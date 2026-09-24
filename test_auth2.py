import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Create a mock login page
        await page.set_content("""
        <html>
        <body>
            <form action="/login" method="post">
                <input type="email" name="email" placeholder="Email">
                <input type="password" name="password" placeholder="Password">
                <button type="submit">Entrar</button>
            </form>
        </body>
        </html>
        """)
        await page.wait_for_timeout(500)
        
        # Import the crawler module's _detect_auth_barrier function logic
        script = """
        () => {
            const result = {
                isLoginPage: false,
                hasCaptcha: false,
                has2FA: false,
                hasEmailVerification: false,
                hasPhoneVerification: false,
                captchaTypes: [],
                blockedSelectors: [],
                pageText: document.body.innerText.slice(0, 5000)
            };
            
            // Login page
            const hasPassword = document.querySelector('input[type="password"]') !== null;
            const hasLoginForm = document.querySelector('form[action*="login" i], form[id*="login" i], form[class*="login" i]') !== null;
            const hasLoginText = /sign in|log in|login|entrar|acessar|sign up|registrar/i.test(document.body.innerText);
            const hasEmailInput = document.querySelector('input[type="email"]') !== null;
            result.isLoginPage = (hasPassword && (hasLoginForm || hasLoginText)) || (hasEmailInput && hasPassword);
            
            // CAPTCHA detection
            const captchaSelectors = [
                'iframe[src*="recaptcha"]',
                'iframe[src*="hcaptcha"]',
                'iframe[src*="captcha"]',
                '.g-recaptcha',
                '.h-captcha',
                '#captcha',
                '[data-captcha]',
                'img[src*="captcha"]',
                '.cf-turnstile',
                '[data-sitekey]'
            ];
            for (const sel of captchaSelectors) {
                if (document.querySelector(sel)) {
                    result.hasCaptcha = true;
                    result.captchaTypes.push(sel);
                }
            }
            
            // 2FA detection
            const twoFAText = /two.?factor|2fa|two.?step|autentica.{0,3}.?dois.?fatores|verifica.{0,3}.?c.{0,3}digo|authenticator|google.?auth|microsoft.?auth|authy/i;
            if (twoFAText.test(document.body.innerText)) {
                result.has2FA = true;
            }
            const twoFAInputs = document.querySelectorAll('input[autocomplete="one-time-code"], input[name*="totp" i], input[name*="2fa" i], input[name*="code" i][maxlength="6"]');
            if (twoFAInputs.length > 0) result.has2FA = true;
            
            // Email verification
            const emailVerifyText = /verif.{0,3}.?email|confirm.{0,3}.?email|check.{0,3}.?inbox|confirma.{0,3}.?e.?mail/i;
            if (emailVerifyText.test(document.body.innerText)) {
                result.hasEmailVerification = true;
            }
            
            // Phone verification
            const phoneVerifyText = /verif.{0,3}.?phone|verif.{0,3}.?celular|confirm.{0,3}.?phone|sms.?code|c.{0,3}digo.?sms/i;
            if (phoneVerifyText.test(document.body.innerText)) {
                result.hasPhoneVerification = true;
            }
            
            // Blocked/Access denied
            const blockedText = /access denied|acesso negado|blocked|bloqueado|forbidden|proibido|rate limit|muitas tentativas|try again later|tente novamente/i;
            if (blockedText.test(document.body.innerText)) {
                result.blockedSelectors.push('page_text');
            }
            
            // Cloudflare/Challenge pages
            if (document.title.includes('Just a moment') || document.title.includes('Checking your browser') || document.querySelector('#challenge-running')) {
                result.hasCaptcha = true;
                result.captchaTypes.push('cloudflare_challenge');
            }
            
            return result;
        }
        """
        result = await page.evaluate(script)
        print('Auth barrier on login page:', result)
        
        # Check if any barrier exists
        has_barrier = any(result.get(k) for k in ["hasCaptcha", "has2FA", "hasEmailVerification", "hasPhoneVerification", "isLoginPage"])
        print('Has barrier:', has_barrier)
        
        await browser.close()

asyncio.run(test())