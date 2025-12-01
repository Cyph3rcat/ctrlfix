"""Price lookup client for part pricing using SerpAPI + Amazon
Real implementation using SerpAPI to scrape Amazon for part prices.
"""
import requests
from dorm_doctor.config import CURRENCY, SERPAPI_API_KEY


class PriceLookupClient:
    """Amazon price lookup client using SerpAPI."""
    
    def __init__(self):
        self.api_key = SERPAPI_API_KEY
        self.base_url = "https://serpapi.com/search"
        
        # Fallback mock prices (if API fails or no results)
        self.fallback_prices = {
            "laptop_screen": 800.0,
            "laptop_battery": 350.0,
            "laptop_keyboard": 200.0,
            "phone_screen": 500.0,
            "phone_battery": 200.0,
            "tablet_screen": 600.0,
            "generic_part": 200.0,
        }
    
    def _search_amazon(self, search_query, max_results=20):
        """Search Amazon using SerpAPI and extract product prices.
        
        Args:
            search_query: Search term (e.g., "samsung s21 lcd replacement")
            max_results: Maximum number of results to analyze
            
        Returns:
            list: List of prices found (floats in USD)
        """
        params = {
            "api_key": self.api_key,
            "engine": "amazon",
            "k": search_query,
            "s": "price-desc-rank"  # Sort by relevance with price priority
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            prices = []
            
            for result in data.get("organic_results", [])[:max_results]:
                price_data = result.get('price', {})
                
                # Handle different price formats
                if isinstance(price_data, dict):
                    raw_price = price_data.get('value') or price_data.get('raw')
                elif isinstance(price_data, str):
                    raw_price = price_data
                else:
                    continue
                
                # Extract numeric price
                if raw_price:
                    try:
                        # Remove $, commas, and convert to float
                        clean_price = str(raw_price).replace('$', '').replace(',', '').strip()
                        price_float = float(clean_price)
                        prices.append(price_float)
                    except (ValueError, TypeError):
                        continue
            
            return prices
            
        except Exception as e:
            print(f"[PriceLookup] ⚠️  Amazon search failed: {e}")
            return []
    
    def get_price(self, device_type, brandmodel, part_name):
        """Get estimated price for a part from Amazon.
        
        Args:
            device_type: Device type (laptop, phone, tablet)
            brandmodel: Combined brand and model string
            part_name: Part name (e.g., 'LCD panel', 'battery')
            
        Returns:
            float: Estimated price in HKD (converted from USD)
        """
        # Build search query
        search_query = f"{brandmodel} {part_name} replacement"
        
        print(f"[PriceLookup] Searching Amazon: '{search_query}'")
        
        # Search Amazon
        prices = self._search_amazon(search_query)
        
        if prices:
            # Calculate average of lowest and highest prices
            lowest = min(prices)
            highest = max(prices)
            average = sum(prices) / len(prices)
            
            # Use average of (lowest + highest) / 2 for conservative estimate
            estimated_usd = (lowest + highest) / 2
            
            # Convert USD to HKD (approximate rate: 1 USD = 7.8 HKD)
            estimated_hkd = estimated_usd * 7.8
            
            print(f"[PriceLookup] Found {len(prices)} prices: ${lowest:.2f} - ${highest:.2f} (avg: ${average:.2f})")
            print(f"[PriceLookup] Estimated cost: ${estimated_usd:.2f} USD = ${estimated_hkd:.2f} HKD")
            
            return estimated_hkd
        else:
            # Fallback to mock price
            print(f"[PriceLookup] ⚠️  No prices found, using fallback")
            part_key = f"{device_type}_{part_name.lower().replace(' ', '_')}"
            return self.fallback_prices.get(part_key, self.fallback_prices["generic_part"])
    
    def estimate_repair_cost(self, device_type, brandmodel, issue_type, parts_needed, description=""):
        """Estimate total repair cost based on device and issue.
        
        Args:
            device_type: Type of device (laptop, phone, tablet)
            brandmodel: Brand and model of device
            issue_type: Issue category (software, hardware, unsure)
            parts_needed: List of parts needed (from diagnostic)
            description: Problem description for better estimation
            
        Returns:
            dict: Breakdown of costs {diagnostic_fee, parts_list, labor, total}
        """
        from dorm_doctor.config import BASE_DIAGNOSTIC_FEE
        
        diagnostic_fee = BASE_DIAGNOSTIC_FEE
        parts_costs = []
        labor_cost = 0.0
        
        if issue_type == "software":
            # Software issues typically don't need parts
            labor_cost = 150.0  # Software troubleshooting/reinstall
        elif issue_type == "hardware":
            # Get real prices for each part
            for part_name in parts_needed:
                part_price = self.get_price(device_type, brandmodel, part_name)
                parts_costs.append({
                    "name": part_name,
                    "price": part_price
                })
            
            # Labor cost varies by complexity (estimate based on parts count)
            labor_cost = 150.0 + (len(parts_needed) * 50.0)  # Base + per-part
        else:  # unsure
            # Provide conservative estimate
            parts_costs.append({
                "name": "Diagnostic & Parts (TBD)",
                "price": 300.0
            })
            labor_cost = 150.0
        
        parts_total = sum(p["price"] for p in parts_costs)
        total = diagnostic_fee + parts_total + labor_cost
        
        return {
            "diagnostic_fee": diagnostic_fee,
            "parts_list": parts_costs,
            "parts_total": parts_total,
            "labor": labor_cost,
            "total": total,
            "currency": CURRENCY
        }


