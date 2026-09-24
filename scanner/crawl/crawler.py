"""Multi-screen crawler with navigation graph."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, parse_qs
from uuid import uuid4

from playwright.async_api import Page, BrowserContext

from ..core.types import Screen, NavGraph, NavEdge, StaticSurface, RuntimeTopology, NetworkCatalogue, StorageInventory, DOMStructure, Selector, Fragility, CapabilityProbeTrace, BehavioralCorrelation, BehavioralPass
from ..core.baseline import get_non_baseline_globals, BASELINE_WINDOW_GLOBALS


@dataclass
class CrawlConfig:
    max_screens: int = 50
    max_depth: int = 5
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=lambda: [
        r".*logout.*", r".*signout.*", r".*login.*", r".*auth.*",
        r".*#.*", r".*\?.*utm_.*", r".*\/api\/.*", r".*\/static\/.*",
        r".*\.(png|jpg|jpeg|gif|svg|css|js|woff|woff2|ttf|eot|ico)(\?.*)?$",
    ])
    timeout_ms: int = 30000
    settle_ms: int = 1500
    behavioral_passes: int = 3


@dataclass
class CrawlState:
    visited_urls: set[str] = field(default_factory=set)
    url_to_screen_id: dict[str, str] = field(default_factory=dict)
    screen_queue: list[tuple[str, int, str | None]] = field(default_factory=list)  # (url, depth, parent_screen_id)
    screens: dict[str, Screen] = field(default_factory=dict)
    edges: list[NavEdge] = field(default_factory=list)
    entry_screen_id: str | None = None


class URLNormalizer:
    """Normalizes URLs to identify distinct screens."""

    # Patterns to remove from URLs for signature
    VOLATILE_PARAMS = frozenset([
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "fbclid", "gclid", "ref", "source", "session", "token", "nonce",
        "timestamp", "ts", "_", "v", "version", "cache", "random", "rand",
    ])

    VOLATILE_PATH_SEGMENTS = [
        r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",  # UUID
        r"/\d{10,}",  # Long numeric IDs
        r"/[A-Za-z0-9_-]{20,}",  # Long alphanumeric IDs
    ]

    @classmethod
    def normalize_url(cls, url: str, base_domain: str) -> str:
        """Normalize URL for screen identification."""
        parsed = urlparse(url)
        # Remove fragment
        path = parsed.path
        # Normalize volatile path segments
        for pattern in cls.VOLATILE_PATH_SEGMENTS:
            path = re.sub(pattern, "/:id", path)
        # Normalize query params
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        filtered = {
            k: v for k, v in query_params.items()
            if k.lower() not in cls.VOLATILE_PARAMS
        }
        # Rebuild query
        query_parts = []
        for k in sorted(filtered.keys()):
            for v in sorted(filtered[k]):
                query_parts.append(f"{k}={v}")
        query = "&".join(query_parts) if query_parts else ""
        # Rebuild URL
        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
        if query:
            normalized += f"?{query}"
        return normalized

    @classmethod
    def url_signature(cls, url: str, base_domain: str) -> str:
        """Generate a stable signature for a URL."""
        normalized = cls.normalize_url(url, base_domain)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    @classmethod
    def should_crawl(cls, url: str, config: CrawlConfig, base_domain: str) -> bool:
        """Check if URL should be crawled."""
        parsed = urlparse(url)
        # Same domain check
        if parsed.netloc != base_domain:
            return False
        # Exclude patterns
        for pattern in config.exclude_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False
        # Include patterns (if specified, must match at least one)
        if config.include_patterns:
            matched = False
            for pattern in config.include_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    matched = True
                    break
            if not matched:
                return False
        return True


class ScreenHasher:
    """Generates DOM structure signatures for screen deduplication."""

    @staticmethod
    async def compute_dom_signature(page: Page) -> str:
        """Compute a hash of the key DOM structure."""
        script = """
        () => {
            // Get key structural elements
            const selectors = [
                '[data-testid]', '[data-test]', '[data-cy]', '[data-qa]',
                '[role]', '[aria-label]', '[aria-labelledby]',
                'main', 'nav', 'aside', 'header', 'footer', 'section',
                'form', 'table', 'ul[class*="list"]', 'ol[class*="list"]',
                '[class*="container"]', '[class*="wrapper"]', '[class*="content"]'
            ];
            const parts = [];
            for (const sel of selectors) {
                const els = document.querySelectorAll(sel);
                for (const el of els) {
                    const tag = el.tagName.toLowerCase();
                    const id = el.id || '';
                    const classes = Array.from(el.classList).filter(c => 
                        !/^[a-z0-9]{5,}$/i.test(c) &&  // filter generated classes
                        !/^(css-|sc-|styled__|emotion-)/.test(c)
                    ).join(' ');
                    const attrs = [];
                    if (el.hasAttribute('data-testid')) attrs.push(`testid="${el.getAttribute('data-testid')}"`);
                    if (el.hasAttribute('role')) attrs.push(`role="${el.getAttribute('role')}"`);
                    if (el.hasAttribute('aria-label')) attrs.push(`aria-label="${el.getAttribute('aria-label')}"`);
                    parts.push(`${tag}${id ? '#' + id : ''}${classes ? '.' + classes : ''}${attrs.length ? '[' + attrs.join(' ') + ']' : ''}`);
                }
            }
            return parts.sort().join('|');
        }
        """
        structure = await page.evaluate(script)
        return hashlib.sha256(structure.encode()).hexdigest()[:16]


class Crawler:
    """Crawls a web application building a navigation graph."""

    def __init__(self, context: BrowserContext, config: CrawlConfig, base_url: str) -> None:
        self.context = context
        self.config = config
        self.base_url = base_url
        parsed = urlparse(base_url)
        self.base_domain = parsed.netloc
        self.state = CrawlState()
        self._page: Page | None = None

    async def __aenter__(self) -> Crawler:
        self._page = await self.context.new_page()
        # Set longer timeout
        self._page.set_default_timeout(self.config.timeout_ms)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._page:
            await self._page.close()

    async def crawl(self, start_url: str | None = None) -> NavGraph:
        """Run the crawl and return the navigation graph."""
        start = start_url or self.base_url
        # Seed the queue
        self.state.screen_queue.append((start, 0, None))

        while self.state.screen_queue and len(self.state.visited_urls) < self.config.max_screens:
            url, depth, parent_id = self.state.screen_queue.pop(0)

            if url in self.state.visited_urls:
                continue
            if depth > self.config.max_depth:
                continue
            if not URLNormalizer.should_crawl(url, self.config, self.base_domain):
                continue

            try:
                screen = await self._visit_screen(url, depth, parent_id)
                if screen:
                    self.state.screens[screen.screen_id] = screen
                    self.state.visited_urls.add(url)
                    self.state.url_to_screen_id[url] = screen.screen_id

                    # Discover links from this screen
                    await self._discover_links(screen)

            except Exception as e:
                print(f"Error visiting {url}: {e}")
                continue

        # Build nav graph
        nav_graph = NavGraph(
            nodes=self.state.screens,
            edges=self.state.edges,
            entry_screen_id=self.state.entry_screen_id,
        )
        return nav_graph

    async def _visit_screen(self, url: str, depth: int, parent_id: str | None) -> Screen | None:
        """Visit a single screen and capture its data."""
        assert self._page is not None
        page = self._page

        # Navigate
        response = await page.goto(url, wait_until="networkidle", timeout=self.config.timeout_ms)
        if not response or response.status >= 400:
            return None

        # Wait for settle
        await page.wait_for_timeout(self.config.settle_ms)

        # Check if authenticated (look for login forms)
        if await self._is_login_page(page):
            print(f"Detected login page at {url}, stopping crawl")
            return None

        # Generate screen ID and signatures
        normalized = URLNormalizer.normalize_url(url, self.base_domain)
        url_sig = URLNormalizer.url_signature(url, self.base_domain)
        dom_sig = await ScreenHasher.compute_dom_signature(page)

        # Check if we've seen this screen structure before (different URL, same structure)
        for existing in self.state.screens.values():
            if existing.dom_signature == dom_sig and existing.url_signature != url_sig:
                # Same screen structure, different URL - treat as transition
                if parent_id:
                    self.state.edges.append(NavEdge(
                        from_screen=parent_id,
                        to_screen=existing.screen_id,
                        action={"type": "navigate", "target": url, "description": f"Navigate to {url}"},
                    ))
                return None

        screen_id = f"scr_{uuid4().hex[:8]}"

        # Capture title
        title = await page.title()

        # Create screen object
        screen = Screen(
            screen_id=screen_id,
            normalized_url=normalized,
            url_signature=url_sig,
            dom_signature=dom_sig,
            title=title,
            depth=depth,
            parent_screen_id=parent_id,
        )

        # Set entry screen
        if self.state.entry_screen_id is None:
            self.state.entry_screen_id = screen_id

        # Add edge from parent
        if parent_id:
            self.state.edges.append(NavEdge(
                from_screen=parent_id,
                to_screen=screen_id,
                action={"type": "navigate", "target": url, "description": f"Navigate from {parent_id}"},
            ))

        # Capture static surface
        screen.static = await self._capture_static_surface(page)

        # Capture runtime topology
        screen.runtime = await self._capture_runtime_topology(page)

        # Capture DOM structure
        screen.dom = await self._capture_dom_structure(page)

        return screen

    async def _is_login_page(self, page: Page) -> bool:
        """Check if current page is a login page."""
        script = """
        () => {
            const hasPassword = document.querySelector('input[type="password"]') !== null;
            const hasLoginForm = document.querySelector('form[action*="login" i], form[id*="login" i], form[class*="login" i]') !== null;
            const hasLoginText = /sign in|log in|login|entrar|acessar/i.test(document.body.innerText);
            return hasPassword && (hasLoginForm || hasLoginText);
        }
        """
        return await page.evaluate(script)

    async def _discover_links(self, screen: Screen) -> None:
        """Discover navigable links from current screen."""
        assert self._page is not None
        page = self._page

        script = """
        () => {
            const links = [];
            // Anchor links
            for (const a of document.querySelectorAll('a[href]')) {
                const href = a.href;
                const text = a.innerText.trim().slice(0, 100);
                const isNav = a.closest('nav, [role="navigation"], [role="menu"], header, aside') !== null;
                const hasStableAttr = a.hasAttribute('data-testid') || a.hasAttribute('data-test') || a.hasAttribute('role');
                links.push({href, text, isNav, hasStableAttr, type: 'anchor'});
            }
            // Buttons that might navigate
            for (const btn of document.querySelectorAll('button, [role="button"], [role="tab"], [role="menuitem"]')) {
                const text = btn.innerText.trim().slice(0, 100);
                const onclick = btn.getAttribute('onclick') || '';
                const routerLink = btn.getAttribute('data-router-link') || btn.getAttribute('href') || '';
                if (text || onclick || routerLink) {
                    links.push({href: routerLink || onclick, text, isNav: false, hasStableAttr: true, type: 'button'});
                }
            }
            // Tabs
            for (const tab of document.querySelectorAll('[role="tab"], [data-tab], [data-tab-id]')) {
                const text = tab.innerText.trim().slice(0, 100);
                const id = tab.getAttribute('data-tab') || tab.getAttribute('data-tab-id') || tab.id;
                links.push({href: `#tab-${id}`, text, isNav: true, hasStableAttr: true, type: 'tab'});
            }
            return links;
        }
        """
        links = await page.evaluate(script)

        for link in links:
            href = link.get("href", "")
            if not href or href.startswith("javascript:") or href.startswith("mailto:") or href.startswith("tel:"):
                continue

            # Resolve relative URLs
            full_url = urljoin(self._page.url, href)

            # Normalize and check
            if not URLNormalizer.should_crawl(full_url, self.config, self.base_domain):
                continue

            normalized = URLNormalizer.normalize_url(full_url, self.base_domain)
            if normalized in self.state.visited_urls or any(normalized == u for u, _, _ in self.state.screen_queue):
                continue

            # Add to queue
            self.state.screen_queue.append((full_url, screen.depth + 1, screen.screen_id))

            # Record action on current screen
            screen.actions.append({
                "type": link["type"],
                "target": link.get("text", href),
                "leads_to_url": full_url,
                "description": f"Click {link['type']}: {link.get('text', href)}",
            })

    async def _capture_static_surface(self, page: Page) -> StaticSurface:
        """Capture static surface: scripts, framework, bundler."""
        script = """
        () => {
            const scripts = [];
            for (const s of document.querySelectorAll('script[src]')) {
                scripts.push({
                    url: s.src,
                    async: s.async,
                    defer: s.defer,
                    type: s.type,
                });
            }
            // Detect framework
            let framework = null, frameworkVersion = null, bundler = null, buildHash = null, moduleSystem = null;

            // React
            if (window.React || window.__REACT_DEVTOOLS_GLOBAL_HOOK__) {
                framework = 'React';
                if (window.React?.version) frameworkVersion = window.React.version;
            }
            // Vue
            else if (window.Vue || window.__VUE_DEVTOOLS_GLOBAL_HOOK__) {
                framework = 'Vue';
                if (window.Vue?.version) frameworkVersion = window.Vue.version;
            }
            // Angular
            else if (window.ng || window.angular || document.querySelector('[ng-app], [ng-version]')) {
                framework = 'Angular';
            }
            // Svelte
            else if (window.__SVELTE_DEVTOOLS_GLOBAL_HOOK__) {
                framework = 'Svelte';
            }
            // Next.js
            if (window.__NEXT_DATA__) {
                framework = 'Next.js';
                frameworkVersion = window.__NEXT_DATA__.buildId;
            }
            // Webpack
            for (const key of Object.keys(window)) {
                if (key.startsWith('webpackChunk')) {
                    bundler = 'Webpack';
                    moduleSystem = 'webpack-require';
                    buildHash = key.replace('webpackChunk', '');
                    break;
                }
            }
            // Vite
            if (window.__vite_plugin_react_preamble_installed__ || window.import.meta?.hot) {
                bundler = bundler || 'Vite';
                moduleSystem = moduleSystem || 'esm';
            }
            // esbuild/Rollup
            if (window.__BUILD_HASH__ || window.__BUILD_TIME__) {
                buildHash = buildHash || window.__BUILD_HASH__;
            }

            return {scripts, framework, frameworkVersion, bundler, buildHash, moduleSystem};
        }
        """
        result = await page.evaluate(script)
        return StaticSurface(
            scripts=result.get("scripts", []),
            framework=result.get("framework"),
            framework_version=result.get("frameworkVersion"),
            bundler=result.get("bundler"),
            build_hash=result.get("buildHash"),
            module_system=result.get("moduleSystem"),
        )

    async def _capture_runtime_topology(self, page: Page) -> RuntimeTopology:
        """Capture runtime topology: globals, module registries, stores."""
        script = """
        () => {
            const baseline = new Set([
                "window","self","document","name","location","history","customElements",
                "locationbar","menubar","personalbar","scrollbars","statusbar","toolbar",
                "status","closed","frames","length","top","opener","parent","frameElement",
                "navigator","origin","external","screen","innerWidth","innerHeight",
                "outerWidth","outerHeight","screenX","screenY","screenLeft","screenTop",
                "scrollX","scrollY","pageXOffset","pageYOffset","visualViewport",
                "devicePixelRatio","clientInformation","defaultStatus","defaultstatus",
                "alert","confirm","prompt","print","open","close","stop","focus","blur",
                "scroll","scrollTo","scrollBy","scrollByLines","scrollByPages",
                "moveTo","moveBy","resizeTo","resizeBy","getComputedStyle","matchMedia",
                "requestAnimationFrame","cancelAnimationFrame","requestIdleCallback",
                "cancelIdleCallback","setTimeout","clearTimeout","setInterval","clearInterval",
                "queueMicrotask","atob","btoa","createImageBitmap","fetch","postMessage",
                "addEventListener","removeEventListener","dispatchEvent","captureEvents",
                "releaseEvents","find","getSelection","showOpenFilePicker","showSaveFilePicker",
                "showDirectoryPicker","launchQueue","secureContext","isSecureContext",
                "performance","PerformanceObserver","PerformanceEntry","PerformanceMark",
                "PerformanceMeasure","PerformanceNavigation","PerformanceNavigationTiming",
                "PerformancePaintTiming","PerformanceResourceTiming","PerformanceTiming",
                "crypto","CryptoKey","SubtleCrypto","isSecureContext","originAgentCluster",
                "crossOriginIsolated","trustedTypes","TrustedTypePolicy","TrustedTypePolicyFactory",
                "TrustToken","FederatedCredential","PasswordCredential","PublicKeyCredential",
                "AuthenticatorAssertionResponse","AuthenticatorAttestationResponse",
                "AuthenticatorResponse","CredentialsContainer","Credential","Authenticator",
                "CredentialCreationOptions","CredentialRequestOptions","PublicKeyCredentialCreationOptions",
                "PublicKeyCredentialRequestOptions","PublicKeyCredentialParameters",
                "PublicKeyCredentialDescriptor","AuthenticatorSelectionCriteria","AuthenticatorTransport",
                "AuthenticatorAttachment","UserVerificationRequirement","ResidentKeyRequirement",
                "AttestationConveyancePreference","AuthenticationExtensionsClientInputs",
                "AuthenticationExtensionsClientOutputs","AuthenticatorData","COSEAlgorithmIdentifier",
                "localStorage","sessionStorage","indexedDB","IDBDatabase","IDBObjectStore",
                "IDBIndex","IDBCursor","IDBCursorWithValue","IDBTransaction","IDBRequest",
                "IDBOpenDBRequest","IDBVersionChangeEvent","IDBKeyRange","IDBFactory",
                "caches","Cache","CacheStorage","console","Console","CSS","CSSStyleDeclaration",
                "CSSRule","CSSStyleRule","CSSMediaRule","CSSSupportsRule","CSSFontFaceRule",
                "CSSKeyframesRule","CSSKeyframeRule","CSSNamespaceRule","CSSPageRule",
                "CSSImportRule","CSSCharsetRule","CSSConditionRule","CSSGroupingRule",
                "StyleSheet","CSSStyleSheet","MediaList","StyleSheetList","Document",
                "DocumentFragment","Element","HTMLElement","HTMLAnchorElement","HTMLAreaElement",
                "HTMLAudioElement","HTMLBaseElement","HTMLBodyElement","HTMLBRElement",
                "HTMLButtonElement","HTMLCanvasElement","HTMLTableCaptionElement",
                "HTMLTableColElement","HTMLTableSectionElement","HTMLTableCellElement",
                "HTMLTableRowElement","HTMLDataElement","HTMLDataListElement",
                "HTMLDetailsElement","HTMLDialogElement","HTMLDirectoryElement","HTMLDivElement",
                "HTMLDListElement","HTMLEmbedElement","HTMLFieldSetElement","HTMLFontElement",
                "HTMLFormElement","HTMLFrameElement","HTMLFrameSetElement","HTMLHeadElement",
                "HTMLHeadingElement","HTMLHtmlElement","HTMLHRElement","HTMLIFrameElement",
                "HTMLImageElement","HTMLInputElement","HTMLLIElement","HTMLLabelElement",
                "HTMLLegendElement","HTMLLinkElement","HTMLMapElement","HTMLMarqueeElement",
                "HTMLMenuElement","HTMLMetaElement","HTMLMeterElement","HTMLModElement",
                "HTMLOListElement","HTMLObjectElement","HTMLOptGroupElement","HTMLOptionElement",
                "HTMLOutputElement","HTMLParagraphElement","HTMLParamElement","HTMLPictureElement",
                "HTMLPreElement","HTMLProgressElement","HTMLQuoteElement","HTMLScriptElement",
                "HTMLSelectElement","HTMLSlotElement","HTMLSourceElement","HTMLSpanElement",
                "HTMLStyleElement","HTMLTableElement","HTMLTemplateElement","HTMLTextAreaElement",
                "HTMLTimeElement","HTMLTitleElement","HTMLTrackElement","HTMLUListElement",
                "HTMLUnknownElement","HTMLVideoElement","SVGElement","SVGSVGElement","SVGGElement",
                "SVGRectElement","SVGCircleElement","SVGEllipseElement","SVGLineElement",
                "SVGPolylineElement","SVGPolygonElement","SVGPathElement","SVGTextElement",
                "SVGImageElement","SVGUseElement","SVGDefsElement","SVGDescElement",
                "SVGMetadataElement","SVGTitleElement","SVGScriptElement","SVGStyleElement",
                "SVGSwitchElement","SVGSymbolElement","SVGMarkerElement","SVGPatternElement",
                "SVGLinearGradientElement","SVGRadialGradientElement","SVGStopElement",
                "SVGClipPathElement","SVGMaskElement","SVGFilterElement","SVGFEBlendElement",
                "SVGFEColorMatrixElement","SVGFEComponentTransferElement","SVGFECompositeElement",
                "SVGFEConvolveMatrixElement","SVGFEDiffuseLightingElement",
                "SVGFEDisplacementMapElement","SVGFEFloodElement","SVGFEFuncAElement",
                "SVGFEFuncBElement","SVGFEFuncGElement","SVGFEFuncRElement",
                "SVGFEGaussianBlurElement","SVGFEImageElement","SVGFEMergeElement",
                "SVGFEMergeNodeElement","SVGFEMorphologyElement","SVGFEOffsetElement",
                "SVGFESpecularLightingElement","SVGFETileElement","SVGFETurbulenceElement",
                "SVGAnimationElement","SVGAnimateElement","SVGAnimateMotionElement",
                "SVGAnimateTransformElement","SVGSetElement","SVGMPatheElement",
                "SVGTextPathElement","SVGTSpanElement","SVGTextContentElement",
                "SVGTextPositioningElement","SVGAElement","SVGForeignObjectElement",
                "Node","NodeList","HTMLCollection","NamedNodeMap","Attr","CharacterData",
                "Text","Comment","ProcessingInstruction","DocumentType","Entity",
                "EntityReference","Notation","XMLDocument","DOMImplementation","DOMTokenList",
                "DOMSettableTokenList","Selection","Range","TreeWalker","NodeIterator",
                "MutationObserver","MutationRecord","IntersectionObserver","IntersectionObserverEntry",
                "ResizeObserver","ResizeObserverEntry","ScrollTimeline","ViewTimeline",
                "AnimationTimeline","Animation","KeyframeEffect","AnimationEffect",
                "GroupEffect","SequenceEffect","ScrollTimelineOptions","ViewTimelineOptions",
                "Event","EventTarget","CustomEvent","MouseEvent","KeyboardEvent","TouchEvent",
                "WheelEvent","DragEvent","ClipboardEvent","FocusEvent","HashChangeEvent",
                "PopStateEvent","PageTransitionEvent","BeforeUnloadEvent","ErrorEvent",
                "PromiseRejectionEvent","ProgressEvent","StorageEvent","TransitionEvent",
                "AnimationEvent","SubmitEvent","FormDataEvent","InputEvent","CompositionEvent",
                "PointerEvent","ToggleEvent","ViewTransitionEvent","XMLHttpRequest",
                "FormData","URLSearchParams","URL","URLPattern","Request","Response","Headers",
                "Body","ReadableStream","WritableStream","TransformStream",
                "ByteLengthQueuingStrategy","CountQueuingStrategy","Blob","File","FileReader",
                "FileList","DataTransfer","DataTransferItem","DataTransferItemList",
                "DragEvent","Clipboard","ClipboardItem","ClipboardEvent","Worker",
                "SharedWorker","ServiceWorker","ServiceWorkerRegistration",
                "ServiceWorkerContainer","ServiceWorkerGlobalScope","Client","Clients",
                "ExtendableEvent","FetchEvent","PushEvent","PushMessageData","SyncEvent",
                "BackgroundFetchEvent","BackgroundFetchRecord","BackgroundFetchRegistration",
                "WindowClient","WorkerGlobalScope","DedicatedWorkerGlobalScope",
                "SharedWorkerGlobalScope","WorkerNavigator","BroadcastChannel","MessageChannel",
                "MessagePort","MessageEvent","CloseEvent","WebGLRenderingContext",
                "WebGL2RenderingContext","WebGLContextAttributes","WebGLShader",
                "WebGLProgram","WebGLBuffer","WebGLFramebuffer","WebGLRenderbuffer",
                "WebGLTexture","WebGLUniformLocation","WebGLActiveInfo",
                "WebGLShaderPrecisionFormat","WebGLContextEvent","WebGLQuery",
                "WebGLSampler","WebGLSync","WebGLTransformFeedback","WebGLVertexArrayObject",
                "OffscreenCanvas","OffscreenCanvasRenderingContext2D","ImageBitmap",
                "ImageBitmapRenderingContext","CanvasRenderingContext2D","CanvasGradient",
                "CanvasPattern","TextMetrics","Path2D","DOMMatrix","DOMMatrixReadOnly",
                "DOMPoint","DOMPointReadOnly","DOMRect","DOMRectReadOnly","DOMQuad",
                "DOMQuadReadOnly","AudioContext","OfflineAudioContext","AudioNode",
                "AudioParam","AudioBuffer","AudioBufferSourceNode",
                "MediaElementAudioSourceNode","MediaStreamAudioSourceNode",
                "MediaStreamAudioDestinationNode","BiquadFilterNode","WaveShaperNode",
                "OscillatorNode","GainNode","DelayNode","PannerNode","StereoPannerNode",
                "ConvolverNode","ChannelMergerNode","ChannelSplitterNode",
                "DynamicsCompressorNode","IIRFilterNode","PeriodicWave","AudioWorkletNode",
                "AudioWorkletGlobalScope","AudioWorkletProcessor","MediaStream",
                "MediaStreamTrack","MediaStreamTrackEvent","MediaDevices","MediaDeviceInfo",
                "MediaStreamConstraints","MediaTrackConstraints","MediaTrackSettings",
                "MediaTrackSupportedConstraints","RTCPeerConnection","RTCSessionDescription",
                "RTCIceCandidate","RTCConfiguration","RTCOfferOptions","RTCAnswerOptions",
                "RTCIceServer","RTCIceTransportPolicy","RTCBundlePolicy","RTCRtcpMuxPolicy",
                "RTCIceCandidateType","RTCPeerConnectionState","RTCIceConnectionState",
                "RTCIceGathererState","RTCSignalingState","RTCStatsReport","RTCDataChannel",
                "RTCDataChannelEvent","RTCDtlsTransport","RTCIceTransport","RTCRtpSender",
                "RTCRtpReceiver","RTCRtpTransceiver","RTCRtpTransceiverDirection",
                "RTCRtpTransceiverInit","RTCRtpEncodingParameters","RTCRtpDecodingParameters",
                "RTCRtpHeaderExtensionCapability","RTCRtpHeaderExtensionParameters",
                "RTCRtpCodecParameters","RTCRtpCapabilities","RTCRtpCodingParameters",
                "RTCDtlsFingerprint","RTCCertificate","RTCCertificateExpiration",
                "WebAssembly","WebAssembly.Module","WebAssembly.Instance","WebAssembly.Memory",
                "WebAssembly.Table","WebAssembly.Global","WebAssembly.CompileError",
                "WebAssembly.LinkError","WebAssembly.RuntimeError","WebAssembly.Tag",
                "WebAssembly.Exception","Intl","Intl.Collator","Intl.DateTimeFormat",
                "Intl.NumberFormat","Intl.PluralRules","Intl.RelativeTimeFormat","Intl.Locale",
                "Intl.Segmenter","Intl.ListFormat","Intl.DisplayNames","Intl.DurationFormat",
                "Array","ArrayBuffer","BigInt","BigInt64Array","BigUint64Array","Boolean",
                "DataView","Date","Error","EvalError","Float32Array","Float64Array",
                "Function","Infinity","Int16Array","Int32Array","Int8Array","JSON",
                "Map","Math","NaN","Number","Object","Promise","Proxy","RangeError",
                "ReferenceError","Reflect","RegExp","Set","SharedArrayBuffer","String",
                "Symbol","SyntaxError","TypeError","Uint16Array","Uint32Array","Uint8Array",
                "Uint8ClampedArray","URIError","WeakMap","WeakRef","WeakSet",
                "decodeURI","decodeURIComponent","encodeURI","encodeURIComponent","escape",
                "unescape","eval","isFinite","isNaN","parseFloat","parseInt","undefined",
                "arguments","this","globalThis","Observable","Observer","Subscription",
                "Subject","BehaviorSubject","ReplaySubject","AsyncSubject",
                "__REACT_DEVTOOLS_GLOBAL_HOOK__","__VUE_DEVTOOLS_GLOBAL_HOOK__",
                "__NUXT_DEVTOOLS_GLOBAL_HOOK__","webpackHotUpdate","webpackChunk_N_E",
                "__NEXT_DATA__","__NEXT_LOADED_PAGES__","__NEXT_LOADED_CHUNKS__",
                "web-vitals","getCLS","getFID","getLCP","getFCP","getTTFB",
                "Zone","__zone_symbol__","Sentry","__SENTRY__"
            ]);

            const ownProps = [];
            for (const key of Object.getOwnPropertyNames(window)) {
                if (!baseline.has(key)) {
                    ownProps.push(key);
                }
            }

            // Module registries
            const moduleRegistries = [];
            for (const key of Object.keys(window)) {
                if (key.startsWith('webpackChunk') || key === '__webpack_require__' || key === 'require' || key === '__NEXT_DATA__') {
                    moduleRegistries.push({
                        type: key.startsWith('webpackChunk') ? 'webpack-chunk' : key,
                        global_name: key,
                        shape: typeof window[key],
                    });
                }
            }

            // State stores (common patterns)
            const stateStores = [];
            const storePatterns = [
                {path: 'window.store', type: 'redux'},
                {path: 'window.Store', type: 'custom'},
                {path: 'window.__STORE__', type: 'custom'},
                {path: 'window.Zustand', type: 'zustand'},
                {path: 'window.MobX', type: 'mobx'},
                {path: 'window.Vuex', type: 'vuex'},
                {path: 'window.Pinia', type: 'pinia'},
            ];
            for (const sp of storePatterns) {
                try {
                    const parts = sp.path.split('.');
                    let obj = window;
                    for (const p of parts.slice(1)) {
                        obj = obj[p];
                    }
                    if (obj) {
                        const keys = Object.keys(obj).slice(0, 20);
                        stateStores.push({path: sp.path, type: sp.type, keys: keys});
                    }
                } catch {}
            }

            // Event bus
            const eventBus = [];
            for (const key of Object.keys(window)) {
                const val = window[key];
                if (val && typeof val === 'object' && typeof val.on === 'function' && typeof val.emit === 'function') {
                    eventBus.push({path: `window.${key}`, methods: ['on', 'emit', 'off']});
                }
            }

            return {ownProps, moduleRegistries, stateStores, eventBus};
        }
        """
        result = await page.evaluate(script)
        return RuntimeTopology(
            window_globals=result.get("ownProps", []),
            module_registries=result.get("moduleRegistries", []),
            state_stores=result.get("stateStores", []),
            event_bus=result.get("eventBus", []),
        )

    async def _capture_dom_structure(self, page: Page) -> DOMStructure:
        """Capture stable DOM selectors and key elements."""
        script = """
        () => {
            const selectors = {};
            const inputTargets = [];
            const listContainers = [];
            const actionButtons = [];

            // Stable selectors
            for (const el of document.querySelectorAll('[data-testid], [data-test], [data-cy], [data-qa], [role], [aria-label]')) {
                let css = '';
                if (el.hasAttribute('data-testid')) css = `[data-testid="${el.getAttribute('data-testid')}"]`;
                else if (el.hasAttribute('data-test')) css = `[data-test="${el.getAttribute('data-test')}"]`;
                else if (el.hasAttribute('data-cy')) css = `[data-cy="${el.getAttribute('data-cy')}"]`;
                else if (el.hasAttribute('data-qa')) css = `[data-qa="${el.getAttribute('data-qa')}"]`;
                else if (el.hasAttribute('role')) css = `[role="${el.getAttribute('role')}"]`;
                else if (el.hasAttribute('aria-label')) css = `[aria-label="${el.getAttribute('aria-label')}"]`;

                if (css) {
                    const key = css.replace(/[\[\]="']/g, '_').replace(/^_|_$/g, '');
                    selectors[key] = {
                        css: css,
                        fragility: 'low',
                        lastVerified: new Date().toISOString().split('T')[0],
                        description: el.tagName.toLowerCase(),
                    };
                }
            }

            // Input targets
            for (const input of document.querySelectorAll('input, textarea, [contenteditable="true"], [role="textbox"]')) {
                const sel = input.getAttribute('data-testid') ? `[data-testid="${input.getAttribute('data-testid')}"`] :
                              input.getAttribute('placeholder') ? `[placeholder="${input.getAttribute('placeholder')}"]` :
                              input.id ? `#${input.id}` : input.tagName.toLowerCase();
                inputTargets.push({selector: sel, type: input.tagName.toLowerCase(), placeholder: input.getAttribute('placeholder') || ''});
            }

            // List containers
            for (const list of document.querySelectorAll('[role="list"], [role="listbox"], [data-list], [data-list-id], ul[class*="list"], ol[class*="list"], table[class*="list"], [class*="message-list"], [class*="conversation-list"], [class*="chat-list"]')) {
                listContainers.push({selector: list.tagName.toLowerCase() + (list.id ? '#' + list.id : ''), tag: list.tagName.toLowerCase()});
            }

            // Action buttons
            for (const btn of document.querySelectorAll('button, [role="button"], input[type="submit"], input[type="button"]')) {
                const text = btn.innerText.trim().slice(0, 50);
                const sel = btn.getAttribute('data-testid') ? `[data-testid="${btn.getAttribute('data-testid')}"]` :
                              btn.id ? `#${btn.id}` : btn.tagName.toLowerCase();
                if (text) {
                    actionButtons.push({selector: sel, text: text, tag: btn.tagName.toLowerCase()});
                }
            }

            return {selectors, inputTargets, listContainers, actionButtons};
        }
        """
        result = await page.evaluate(script)

        stable_selectors = {}
        for k, v in result.get("selectors", {}).items():
            stable_selectors[k] = Selector(
                css=v["css"],
                fragility=Fragility(v["fragility"]),
                last_verified=v["lastVerified"],
                description=v["description"],
            )

        return DOMStructure(
            stable_selectors=stable_selectors,
            input_targets=result.get("inputTargets", []),
            list_containers=result.get("listContainers", []),
            action_buttons=result.get("actionButtons", []),
        )


async def run_behavioral_correlation(page: Page, action_name: str, action_fn, config: CrawlConfig) -> BehavioralCorrelation:
    """Run behavioral correlation for a specific action."""
    from ..core.baseline import BASELINE_WINDOW_GLOBALS

    passes: list[BehavioralPass] = []

    for pass_num in range(config.behavioral_passes):
        # Baseline snapshot
        baseline = await page.evaluate("""
            () => {
                const state = {};
                for (const key of Object.keys(window)) {
                    const val = window[key];
                    if (val && typeof val === 'object' && val !== null) {
                        try {
                            state[key] = JSON.stringify(val).slice(0, 200);
                        } catch {
                            state[key] = typeof val;
                        }
                    }
                }
                return state;
            }
        """)

        # Network baseline
        net_before = []

        # Execute action
        await action_fn(page)
        await page.wait_for_timeout(config.settle_ms)

        # After snapshot
        after = await page.evaluate("""
            () => {
                const state = {};
                for (const key of Object.keys(window)) {
                    const val = window[key];
                    if (val && typeof val === 'object' && val !== null) {
                        try {
                            state[key] = JSON.stringify(val).slice(0, 200);
                        } catch {
                            state[key] = typeof val;
                        }
                    }
                }
                return state;
            }
        """)

        # Compare
        changed = []
        for key in set(list(baseline.keys()) + list(after.keys())):
            if baseline.get(key) != after.get(key):
                changed.append(key)

        # DOM mutations (simplified)
        dom_mutations = await page.evaluate("""
            () => {
                const mutations = [];
                const observer = new MutationObserver(muts => {
                    for (const m of muts) {
                        mutations.push({type: m.type, target: m.target.tagName, attribute: m.attributeName});
                    }
                });
                observer.observe(document.body, {childList: true, subtree: true, attributes: true});
                return () => mutations;
            }
        """)
        # Note: This is a simplified approach; real impl would use CDP or proper observer

        passes.append(BehavioralPass(
            action=action_name,
            pass_number=pass_num + 1,
            changed_handles=changed,
            network_delta=net_before,
            dom_mutations=[],
            duration_ms=config.settle_ms,
        ))

        # Reset (navigate back or undo)
        await page.go_back()
        await page.wait_for_timeout(config.settle_ms)

    # Intersect handles that changed on ALL passes
    if passes:
        intersected = set(passes[0].changed_handles)
        for p in passes[1:]:
            intersected &= set(p.changed_handles)
    else:
        intersected = set()

    # Noise floor: run a no-op action
    noise_handles = set()
    # (Simplified - would run a no-op like scrolling slightly)

    ranked = []
    for handle in intersected - noise_handles:
        ranked.append({"handle": handle, "specificity": 1.0, "confidence": 0.8})

    return BehavioralCorrelation(
        action=action_name,
        passes=passes,
        intersected_handles=list(intersected),
        noise_floor_handles=list(noise_handles),
        ranked_candidates=ranked,
    )