import asyncio
from playwright.async_api import async_playwright
from scanner.crawl.crawler import Crawler, CrawlConfig, URLNormalizer

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
        
        config = CrawlConfig()
        crawler = Crawler(context, config, "http://localhost")
        
        # Use set_content instead of goto
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
        await page.wait_for_timeout(config.settle_ms)
        
        # Test the _detect_auth_barrier method
        auth_barrier = await crawler._detect_auth_barrier(page)
        print('Auth barrier:', auth_barrier)
        
        # Check if login page
        is_login = await crawler._is_login_page(page)
        print('Is login page:', is_login)
        
        # Check if it would create a screen with auth_barrier
        has_barrier = any(auth_barrier.get(k) for k in ["hasCaptcha", "has2FA", "hasEmailVerification", "hasPhoneVerification", "isLoginPage"])
        print('Has barrier:', has_barrier)
        
        await browser.close()

asyncio.run(test())