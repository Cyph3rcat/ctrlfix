"""Test SerpAPI connection with Amazon search
Testing search query: 'samsung s21 lcd replacement'
"""
import requests
import json
from dorm_doctor.config import SERPAPI_API_KEY

def test_serpapi_amazon(search_query):
    """Test SerpAPI Amazon search and display JSON response"""
    
    print(f"Testing SerpAPI with Amazon...")
    print(f"Search query: {search_query}")
    print(f"API Key: {SERPAPI_API_KEY[:20]}...")
    print("-" * 60)
    
    # SerpAPI endpoint for Amazon
    url = "https://serpapi.com/search"
    
    params = {
        "api_key": SERPAPI_API_KEY,
        "engine": "amazon",
        "k": search_query,  # Amazon uses 'search_term', not 'q'
        "s" : "price-desc-rank"
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Save full response to file for inspection
        with open("amazon_response_full.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("✅ Full response saved to: amazon_response_full.json")
        
        # Extract and display organic results (product listings)
        if "organic_results" in data:
            print(f"\n📦 Found {len(data['organic_results'])} products")
            print("\n" + "="*60)
            
            # Collect all product data
            products_list = []
            
            for idx, result in enumerate(data.get("organic_results", []), 1):
                # Extract all relevant fields
                product = {
                    "title": result.get('title', 'N/A'),
                    "asin": result.get('asin', 'N/A'),
                    "thumbnail": result.get('thumbnail', 'N/A'),
                    "price": result.get('price', 'N/A'),
                    "rating": result.get('rating', 'N/A'),
                    "reviews": result.get('reviews', 'N/A'),
                    "link": result.get('link', 'N/A')
                }
                
                products_list.append(product)
                
                # Print to terminal
                print(f"\n[{idx}] Product JSON:")
                print(json.dumps(product, indent=2, ensure_ascii=False))
            
            print("\n" + "="*60)
            
            # Extract just prices for analysis
            prices = []
            for product in products_list:
                price_data = product.get('price', {})
                if isinstance(price_data, dict):
                    raw_price = price_data.get('value') or price_data.get('raw')
                elif isinstance(price_data, str):
                    raw_price = price_data
                else:
                    continue
                
                # Try to extract numeric price
                if raw_price:
                    try:
                        # Remove $ and , then convert to float
                        clean_price = str(raw_price).replace('$', '').replace(',', '').strip()
                        price_float = float(clean_price)
                        prices.append(price_float)
                    except (ValueError, TypeError):
                        pass
            
            if prices:
                print(f"\n💰 Price Analysis:")
                print(f"    Total prices found: {len(prices)}")
                print(f"    Lowest: ${min(prices):.2f}")
                print(f"    Highest: ${max(prices):.2f}")
                print(f"    Average: ${sum(prices)/len(prices):.2f}")
                
                # Save prices to separate file
                with open("amazon_prices.json", "w") as f:
                    json.dump({
                        "query": search_query,
                        "prices": prices,
                        "lowest": min(prices),
                        "highest": max(prices),
                        "average": sum(prices)/len(prices)
                    }, f, indent=2)
                print(f"    💾 Price data saved to: amazon_prices.json")
            else:
                print("\n⚠️  No prices found in results")
        
        else:
            print("\n⚠️  No organic_results in response")
            print(f"Available keys: {list(data.keys())}")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Request failed: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"\n❌ JSON decode error: {e}")
        print(f"Response text: {response.text[:500]}")
        return None

if __name__ == "__main__":
    # Test with Samsung S21 LCD replacement
    result = test_serpapi_amazon("samsung s21 lcd replacement")
    
    if result:
        print("\n✅ Test completed successfully!")
    else:
        print("\n❌ Test failed!")
