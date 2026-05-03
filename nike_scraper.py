from playwright.sync_api import sync_playwright, TimeoutError
import pandas as pd
import time
import re

BASE_URL = "https://www.nike.com/ph/w"
OUTPUT_CSV = "nike_products.csv"
TOP20_CSV = "top_20_rating_review.csv"


def clean_price(text):
    if not text:
        return None
    text = re.sub(r"[^\d.]", "", text)
    return float(text) if text else None


def scrape_nike():
    products = []
    empty_tagging_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800}
        )

        page = context.new_page()

        print("Opening Nike page...")

        try:
            page.goto(
                BASE_URL,
                timeout=90000,
                wait_until="domcontentloaded"
            )
        except TimeoutError:
            print("Initial load slow, continuing anyway...")

        # Give Nike JS time to hydrate
        time.sleep(6)

        # Scroll to load all products
        previous_height = 0
        for _ in range(15):
            page.mouse.wheel(0, 4000)
            time.sleep(2)
            height = page.evaluate("document.body.scrollHeight")
            if height == previous_height:
                break
            previous_height = height

        cards = page.locator("div.product-card")
        count = cards.count()
        print(f"Total products found: {count}")

        for i in range(count):
            card = cards.nth(i)
            try:
                name = card.locator("div.product-card__title").inner_text(timeout=2000)
                desc = card.locator("div.product-card__subtitle").inner_text(timeout=2000)

                link = card.locator("a").get_attribute("href")
                image = card.locator("img").get_attribute("src")

                tag = ""
                if card.locator("div.product-card__badge").count() > 0:
                    tag = card.locator("div.product-card__badge").inner_text().strip()

                if not tag:
                    empty_tagging_count += 1
                    continue

                prices = card.locator("div.product-price")
                original_price = None
                discount_price = None

                if prices.count() == 2:
                    original_price = clean_price(prices.nth(0).inner_text())
                    discount_price = clean_price(prices.nth(1).inner_text())
                elif prices.count() == 1:
                    discount_price = clean_price(prices.nth(0).inner_text())

                if not discount_price:
                    continue

                products.append({
                    "Product_URL": f"https://www.nike.com{link}",
                    "Product_Image_URL": image,
                    "Product_Tagging": tag,
                    "Product_Name": name,
                    "Product_Description": desc,
                    "Original_Price": original_price,
                    "Discount_Price": discount_price,
                    "Sizes_Available": "",
                    "Vouchers": "",
                    "Available_Colors": "",
                    "Color_Shown": "",
                    "Style_Code": "",
                    "Rating_Score": 0,
                    "Review_Count": 0
                })

            except Exception:
                continue

        browser.close()

    print(f"Total products with empty tagging: {empty_tagging_count}")

    if not products:
        print("No products found. Exiting gracefully.")
        return

    df = pd.DataFrame(products)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved {len(df)} products to {OUTPUT_CSV}")

    # -------- Top 10 Expensive --------
    top10 = df.sort_values("Discount_Price", ascending=False).head(10)

    print("\nTop 10 Most Expensive Products:")
    for _, row in top10.iterrows():
        print(f"{row['Product_Name']} | {row['Discount_Price']} | {row['Product_URL']}")

    # -------- Top 20 Rating + Reviews --------
    eligible = df[df["Review_Count"] > 150]
    ranked = eligible.sort_values(
        by=["Rating_Score", "Review_Count"],
        ascending=[False, False]
    ).head(20)

    ranked.to_csv(TOP20_CSV, index=False)
    print(f"\nSaved top 20 ranked products to {TOP20_CSV}")


if __name__ == "__main__":
    scrape_nike()
