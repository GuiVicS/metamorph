import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
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
        
        # Test auth barrier detection
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
            };
            
            const hasPassword = document.querySelector('input[type="password"]') !== null;
            const hasLoginForm = document.querySelector('form[action*="login" i], form[id*="login" i], form[class*="login" i]') !== null;
            const hasLoginText = /sign in|log in|login|entrar|acessar|sign up|registrar/i.test(document.body.innerText);
            const hasEmailInput = document.querySelector('input[type="email"]') !== null;
            result.isLoginPage = (hasPassword && (hasLoginForm || hasLoginText)) || (hasEmailInput && hasPassword);
            
            return result;
        }
        """
        result = await page.evaluate(script)
        print('Login page test:', result)
        
        # Test CAPTCHA detection
        await page.set_content("""
        <html>
        <body>
            <div class="g-recaptcha" data-sitekey="test"></div>
        </body>
        </html>
        """)
        await page.wait_for_timeout(500)
        
        script2 = """
        () => {
            const result = { hasCaptcha: false, captchaTypes: [] };
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
            return result;
        }
        """
        result2 = await page.evaluate(script2)
        print('CAPTCHA test:', result2)
        
        await browser.close()

asyncio.run(test())