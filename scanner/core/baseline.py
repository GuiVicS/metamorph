"""Clean browser baseline for detecting non-standard globals."""

# Baseline globals present in a clean Chrome context
# Source: MDN + Chrome 116+ baseline

BASELINE_WINDOW_GLOBALS = frozenset([
    # Standard window properties
    "window", "self", "document", "name", "location", "history", "customElements",
    "locationbar", "menubar", "personalbar", "scrollbars", "statusbar", "toolbar",
    "status", "closed", "frames", "length", "top", "opener", "parent", "frameElement",
    "navigator", "origin", "external", "screen", "innerWidth", "innerHeight",
    "outerWidth", "outerHeight", "screenX", "screenY", "screenLeft", "screenTop",
    "scrollX", "scrollY", "pageXOffset", "pageYOffset", "visualViewport",
    "devicePixelRatio", "clientInformation", "defaultStatus", "defaultstatus",

    # Standard methods
    "alert", "confirm", "prompt", "print", "open", "close", "stop", "focus", "blur",
    "scroll", "scrollTo", "scrollBy", "scrollByLines", "scrollByPages",
    "moveTo", "moveBy", "resizeTo", "resizeBy", "getComputedStyle", "matchMedia",
    "requestAnimationFrame", "cancelAnimationFrame", "requestIdleCallback",
    "cancelIdleCallback", "setTimeout", "clearTimeout", "setInterval", "clearInterval",
    "queueMicrotask", "atob", "btoa", "createImageBitmap", "fetch", "postMessage",
    "addEventListener", "removeEventListener", "dispatchEvent", "captureEvents",
    "releaseEvents", "find", "getSelection", "showOpenFilePicker", "showSaveFilePicker",
    "showDirectoryPicker", "launchQueue", "secureContext", "isSecureContext",

    # Performance & timing
    "performance", "PerformanceObserver", "PerformanceEntry", "PerformanceMark",
    "PerformanceMeasure", "PerformanceNavigation", "PerformanceNavigationTiming",
    "PerformancePaintTiming", "PerformanceResourceTiming", "PerformanceTiming",

    # Crypto & security
    "crypto", "CryptoKey", "SubtleCrypto", "isSecureContext", "originAgentCluster",
    "crossOriginIsolated", "trustedTypes", "TrustedTypePolicy", "TrustedTypePolicyFactory",
    "trustedTypes", "TrustToken", "FederatedCredential", "PasswordCredential",
    "PublicKeyCredential", "AuthenticatorAssertionResponse", "AuthenticatorAttestationResponse",
    "AuthenticatorResponse", "CredentialsContainer", "Credential", "Authenticator",
    "CredentialCreationOptions", "CredentialRequestOptions", "PublicKeyCredentialCreationOptions",
    "PublicKeyCredentialRequestOptions", "PublicKeyCredentialParameters",
    "PublicKeyCredentialDescriptor", "AuthenticatorSelectionCriteria", "AuthenticatorTransport",
    "AuthenticatorAttachment", "UserVerificationRequirement", "ResidentKeyRequirement",
    "AttestationConveyancePreference", "AuthenticationExtensionsClientInputs",
    "AuthenticationExtensionsClientOutputs", "AuthenticatorData", "COSEAlgorithmIdentifier",

    # Storage
    "localStorage", "sessionStorage", "indexedDB", "IDBDatabase", "IDBObjectStore",
    "IDBIndex", "IDBCursor", "IDBCursorWithValue", "IDBTransaction", "IDBRequest",
    "IDBOpenDBRequest", "IDBVersionChangeEvent", "IDBKeyRange", "IDBFactory",
    "caches", "Cache", "CacheStorage",

    # Web APIs
    "console", "Console", "CSS", "CSSStyleDeclaration", "CSSRule", "CSSStyleRule",
    "CSSMediaRule", "CSSSupportsRule", "CSSFontFaceRule", "CSSKeyframesRule",
    "CSSKeyframeRule", "CSSNamespaceRule", "CSSPageRule", "CSSImportRule",
    "CSSCharsetRule", "CSSConditionRule", "CSSGroupingRule", "StyleSheet",
    "CSSStyleSheet", "MediaList", "StyleSheetList", "Document", "DocumentFragment",
    "Element", "HTMLElement", "HTMLAnchorElement", "HTMLAreaElement", "HTMLAudioElement",
    "HTMLBaseElement", "HTMLBodyElement", "HTMLBRElement", "HTMLButtonElement",
    "HTMLCanvasElement", "HTMLTableCaptionElement", "HTMLTableColElement",
    "HTMLTableSectionElement", "HTMLTableCellElement", "HTMLTableRowElement",
    "HTMLDataElement", "HTMLDataListElement", "HTMLDetailsElement", "HTMLDialogElement",
    "HTMLDirectoryElement", "HTMLDivElement", "HTMLDListElement", "HTMLEmbedElement",
    "HTMLFieldSetElement", "HTMLFontElement", "HTMLFormElement", "HTMLFrameElement",
    "HTMLFrameSetElement", "HTMLHeadElement", "HTMLHeadingElement", "HTMLHtmlElement",
    "HTMLHRElement", "HTMLIFrameElement", "HTMLImageElement", "HTMLInputElement",
    "HTMLLIElement", "HTMLLabelElement", "HTMLLegendElement", "HTMLLinkElement",
    "HTMLMapElement", "HTMLMarqueeElement", "HTMLMenuElement", "HTMLMetaElement",
    "HTMLMeterElement", "HTMLModElement", "HTMLOListElement", "HTMLObjectElement",
    "HTMLOptGroupElement", "HTMLOptionElement", "HTMLOutputElement", "HTMLParagraphElement",
    "HTMLParamElement", "HTMLPictureElement", "HTMLPreElement", "HTMLProgressElement",
    "HTMLQuoteElement", "HTMLScriptElement", "HTMLSelectElement", "HTMLSlotElement",
    "HTMLSourceElement", "HTMLSpanElement", "HTMLStyleElement", "HTMLTableElement",
    "HTMLTemplateElement", "HTMLTextAreaElement", "HTMLTimeElement", "HTMLTitleElement",
    "HTMLTrackElement", "HTMLUListElement", "HTMLUnknownElement", "HTMLVideoElement",
    "SVGElement", "SVGSVGElement", "SVGGElement", "SVGRectElement", "SVGCircleElement",
    "SVGEllipseElement", "SVGLineElement", "SVGPolylineElement", "SVGPolygonElement",
    "SVGPathElement", "SVGTextElement", "SVGImageElement", "SVGUseElement",
    "SVGDefsElement", "SVGDescElement", "SVGMetadataElement", "SVGTitleElement",
    "SVGScriptElement", "SVGStyleElement", "SVGSwitchElement", "SVGSymbolElement",
    "SVGMarkerElement", "SVGPatternElement", "SVGLinearGradientElement",
    "SVGRadialGradientElement", "SVGStopElement", "SVGClipPathElement",
    "SVGMaskElement", "SVGFilterElement", "SVGFEBlendElement", "SVGFEColorMatrixElement",
    "SVGFEComponentTransferElement", "SVGFECompositeElement", "SVGFEConvolveMatrixElement",
    "SVGFEDiffuseLightingElement", "SVGFEDisplacementMapElement", "SVGFEFloodElement",
    "SVGFEFuncAElement", "SVGFEFuncBElement", "SVGFEFuncGElement", "SVGFEFuncRElement",
    "SVGFEGaussianBlurElement", "SVGFEImageElement", "SVGFEMergeElement",
    "SVGFEMergeNodeElement", "SVGFEMorphologyElement", "SVGFEOffsetElement",
    "SVGFESpecularLightingElement", "SVGFETileElement", "SVGFETurbulenceElement",
    "SVGAnimationElement", "SVGAnimateElement", "SVGAnimateMotionElement",
    "SVGAnimateTransformElement", "SVGSetElement", "SVGMPatheElement", "SVGTextPathElement",
    "SVGTSpanElement", "SVGTextContentElement", "SVGTextPositioningElement",
    "SVGAElement", "SVGForeignObjectElement", "SVGClipPathElement", "SVGMaskElement",

    # DOM APIs
    "Node", "NodeList", "HTMLCollection", "NamedNodeMap", "Attr", "CharacterData",
    "Text", "Comment", "ProcessingInstruction", "DocumentType", "Entity", "EntityReference",
    "Notation", "Document", "XMLDocument", "DOMImplementation", "DOMTokenList",
    "DOMSettableTokenList", "Selection", "Range", "TreeWalker", "NodeIterator",
    "MutationObserver", "MutationRecord", "IntersectionObserver", "IntersectionObserverEntry",
    "ResizeObserver", "ResizeObserverEntry", "ScrollTimeline", "ViewTimeline",
    "AnimationTimeline", "Animation", "KeyframeEffect", "AnimationEffect",
    "GroupEffect", "SequenceEffect", "ScrollTimelineOptions", "ViewTimelineOptions",

    # Events
    "Event", "EventTarget", "CustomEvent", "MouseEvent", "KeyboardEvent", "TouchEvent",
    "WheelEvent", "DragEvent", "ClipboardEvent", "FocusEvent", "HashChangeEvent",
    "PopStateEvent", "PageTransitionEvent", "BeforeUnloadEvent", "ErrorEvent",
    "PromiseRejectionEvent", "ProgressEvent", "StorageEvent", "TransitionEvent",
    "AnimationEvent", "SubmitEvent", "FormDataEvent", "InputEvent", "CompositionEvent",
    "PointerEvent", "SubmitEvent", "ToggleEvent", "ViewTransitionEvent",

    # Network
    "XMLHttpRequest", "FormData", "URLSearchParams", "URL", "URLPattern",
    "Request", "Response", "Headers", "Body", "ReadableStream", "WritableStream",
    "TransformStream", "ByteLengthQueuingStrategy", "CountQueuingStrategy",
    "Blob", "File", "FileReader", "FileList", "DataTransfer", "DataTransferItem",
    "DataTransferItemList", "DragEvent", "Clipboard", "ClipboardItem", "ClipboardEvent",

    # Web Workers
    "Worker", "SharedWorker", "ServiceWorker", "ServiceWorkerRegistration",
    "ServiceWorkerContainer", "ServiceWorkerGlobalScope", "Client", "Clients",
    "ExtendableEvent", "FetchEvent", "PushEvent", "PushMessageData", "SyncEvent",
    "BackgroundFetchEvent", "BackgroundFetchRecord", "BackgroundFetchRegistration",
    "CacheStorage", "Cache", "WindowClient", "WorkerGlobalScope", "DedicatedWorkerGlobalScope",
    "SharedWorkerGlobalScope", "WorkerNavigator", "BroadcastChannel", "MessageChannel",
    "MessagePort", "MessageEvent", "CloseEvent",

    # WebGL / Canvas
    "WebGLRenderingContext", "WebGL2RenderingContext", "WebGLContextAttributes",
    "WebGLShader", "WebGLProgram", "WebGLBuffer", "WebGLFramebuffer", "WebGLRenderbuffer",
    "WebGLTexture", "WebGLUniformLocation", "WebGLActiveInfo", "WebGLShaderPrecisionFormat",
    "WebGLContextEvent", "WebGLQuery", "WebGLSampler", "WebGLSync", "WebGLTransformFeedback",
    "WebGLVertexArrayObject", "OffscreenCanvas", "OffscreenCanvasRenderingContext2D",
    "ImageBitmap", "ImageBitmapRenderingContext", "CanvasRenderingContext2D",
    "CanvasGradient", "CanvasPattern", "TextMetrics", "Path2D", "DOMMatrix", "DOMMatrixReadOnly",
    "DOMPoint", "DOMPointReadOnly", "DOMRect", "DOMRectReadOnly", "DOMQuad", "DOMQuadReadOnly",

    # Audio / Video
    "AudioContext", "OfflineAudioContext", "AudioNode", "AudioParam", "AudioBuffer",
    "AudioBufferSourceNode", "MediaElementAudioSourceNode", "MediaStreamAudioSourceNode",
    "MediaStreamAudioDestinationNode", "BiquadFilterNode", "WaveShaperNode", "OscillatorNode",
    "GainNode", "DelayNode", "PannerNode", "StereoPannerNode", "ConvolverNode",
    "ChannelMergerNode", "ChannelSplitterNode", "DynamicsCompressorNode", "IIRFilterNode",
    "PeriodicWave", "AudioWorkletNode", "AudioWorkletGlobalScope", "AudioWorkletProcessor",
    "MediaStream", "MediaStreamTrack", "MediaStreamTrackEvent", "MediaDevices",
    "MediaDeviceInfo", "MediaStreamConstraints", "MediaTrackConstraints", "MediaTrackSettings",
    "MediaTrackSupportedConstraints", "RTCPeerConnection", "RTCSessionDescription",
    "RTCIceCandidate", "RTCConfiguration", "RTCOfferOptions", "RTCAnswerOptions",
    "RTCIceServer", "RTCIceTransportPolicy", "RTCBundlePolicy", "RTCRtcpMuxPolicy",
    "RTCIceCandidateType", "RTCPeerConnectionState", "RTCIceConnectionState",
    "RTCIceGathererState", "RTCSignalingState", "RTCStatsReport", "RTCDataChannel",
    "RTCDataChannelEvent", "RTCDtlsTransport", "RTCIceTransport", "RTCRtpSender",
    "RTCRtpReceiver", "RTCRtpTransceiver", "RTCRtpTransceiverDirection",
    "RTCRtpTransceiverInit", "RTCRtpEncodingParameters", "RTCRtpDecodingParameters",
    "RTCRtpHeaderExtensionCapability", "RTCRtpHeaderExtensionParameters",
    "RTCRtpCodecParameters", "RTCRtpCapabilities", "RTCRtpCodingParameters",
    "RTCDtlsFingerprint", "RTCCertificate", "RTCCertificateExpiration",

    # WebAssembly
    "WebAssembly", "WebAssembly.Module", "WebAssembly.Instance", "WebAssembly.Memory",
    "WebAssembly.Table", "WebAssembly.Global", "WebAssembly.CompileError",
    "WebAssembly.LinkError", "WebAssembly.RuntimeError", "WebAssembly.Tag",
    "WebAssembly.Exception",

    # Internationalization
    "Intl", "Intl.Collator", "Intl.DateTimeFormat", "Intl.NumberFormat",
    "Intl.PluralRules", "Intl.RelativeTimeFormat", "Intl.Locale", "Intl.Segmenter",
    "Intl.ListFormat", "Intl.DisplayNames", "Intl.DurationFormat",

    # Other globals
    "Array", "ArrayBuffer", "BigInt", "BigInt64Array", "BigUint64Array", "Boolean",
    "DataView", "Date", "Error", "EvalError", "Float32Array", "Float64Array",
    "Function", "Infinity", "Int16Array", "Int32Array", "Int8Array", "Intl",
    "JSON", "Map", "Math", "NaN", "Number", "Object", "Promise", "Proxy",
    "RangeError", "ReferenceError", "Reflect", "RegExp", "Set", "SharedArrayBuffer",
    "String", "Symbol", "SyntaxError", "TypeError", "Uint16Array", "Uint32Array",
    "Uint8Array", "Uint8ClampedArray", "URIError", "WeakMap", "WeakRef", "WeakSet",
    "decodeURI", "decodeURIComponent", "encodeURI", "encodeURIComponent", "escape",
    "unescape", "eval", "isFinite", "isNaN", "parseFloat", "parseInt", "undefined",
    "arguments", "this", "console", "globalThis",

    # Observables
    "Observable", "Observer", "Subscription", "Subject", "BehaviorSubject",
    "ReplaySubject", "AsyncSubject",

    # Common framework/runtime globals (often present even in clean context)
    "__REACT_DEVTOOLS_GLOBAL_HOOK__", "__VUE_DEVTOOLS_GLOBAL_HOOK__",
    "__NUXT_DEVTOOLS_GLOBAL_HOOK__", "webpackHotUpdate", "webpackChunk_N_E",
    "__NEXT_DATA__", "__NEXT_LOADED_PAGES__", "__NEXT_LOADED_CHUNKS__",

    # Web Vitals
    "web-vitals", "getCLS", "getFID", "getLCP", "getFCP", "getTTFB",

    # Zone.js (Angular)
    "Zone", "__zone_symbol__",

    # Sentry
    "Sentry", "__SENTRY__",
])


# Baseline properties on document
BASELINE_DOCUMENT_GLOBALS = frozenset([
    "documentElement", "head", "body", "title", "characterSet", "charset",
    "contentType", "doctype", "documentURI", "URL", "domain", "referrer",
    "cookie", "lastModified", "readyState", "visibilityState", "hidden",
    "fullscreenElement", "fullscreenEnabled", "pointerLockElement",
    "scripts", "stylesheets", "images", "links", "forms", "anchors",
    "applets", "embeds", "plugins", "pictures", "currentScript",
    "scrollingElement", "timeline", "defaultView", "implementation",
    "compatMode", "dir", "all", "getElementById", "getElementsByClassName",
    "getElementsByName", "getElementsByTagName", "getElementsByTagNameNS",
    "querySelector", "querySelectorAll", "createElement", "createElementNS",
    "createDocumentFragment", "createTextNode", "createComment", "createCDATASection",
    "createProcessingInstruction", "createAttribute", "createAttributeNS",
    "createEvent", "createRange", "createNodeIterator", "createTreeWalker",
    "createExpression", "createNSResolver", "evaluate", "adoptNode", "importNode",
    "createProcessingInstruction", "hasFocus", "open", "close", "write", "writeln",
    "execCommand", "queryCommandEnabled", "queryCommandIndeterm", "queryCommandState",
    "queryCommandSupported", "queryCommandValue", "getSelection",
    "elementFromPoint", "elementsFromPoint", "caretPositionFromPoint",
    "caretRangeFromPoint", "releaseEvents", "captureEvents", "addEventListener",
    "removeEventListener", "dispatchEvent",
])


# Baseline properties on navigator
BASELINE_NAVIGATOR_GLOBALS = frozenset([
    "userAgent", "appVersion", "platform", "vendor", "product", "language",
    "languages", "onLine", "cookieEnabled", "javaEnabled", "taintEnabled",
    "geolocation", "permissions", "clipboard", "credentials", "keyboard",
    "mediaDevices", "mediaSession", "storage", "serviceWorker", "userAgentData",
    "deviceMemory", "hardwareConcurrency", "maxTouchPoints", "connection",
    "bluetooth", "usb", "serial", "hid", "presentation", "xr", "wakeLock",
    "scheduling", "virtualKeyboard", "windowControlsOverlay", "mediaCapabilities",
    "locks", "devicePosture", "pdfViewerEnabled", "pdfViewerEnabled",
    "getBattery", "getGamepads", "getVRDisplays", "sendBeacon", "share",
    "canShare", "registerProtocolHandler", "unregisterProtocolHandler",
    "vibrate", "getAutoplayPolicy", "requestMediaKeySystemAccess",
])


def is_baseline_global(name: str) -> bool:
    """Check if a global name is part of the clean browser baseline."""
    return name in BASELINE_WINDOW_GLOBALS


def get_non_baseline_globals(observed: list[str]) -> list[str]:
    """Filter observed globals to only non-baseline ones."""
    return [g for g in observed if g not in BASELINE_WINDOW_GLOBALS]