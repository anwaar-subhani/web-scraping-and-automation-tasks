"""JavaScript code strings for page evaluation"""
# JavaScript code to extract product links from search results page
GET_PRODUCT_LINKS_SCRIPT = """
() => {
    const links = [];
    const processedHrefs = new Set();
    const processedAsins = new Set();
    
    // Method 1: Standard search results (including sponsored)
    const searchResults = document.querySelectorAll('[data-component-type="s-search-result"]');
    console.log('Standard search results found:', searchResults.length);
    
    searchResults.forEach((product, index) => {
        const asin = product.getAttribute('data-asin');
        
        // Try multiple selectors for the product link
        let link = product.querySelector('h2 a');
        if (!link) link = product.querySelector('a[href*="/dp/"]');
        if (!link) link = product.querySelector('a[href*="/-/en/"]');
        if (!link) link = product.querySelector('a[href*="/gp/product/"]');
        
        if (link) {
            const href = link.getAttribute('href');
            const title = link.textContent?.trim() || 'No title';
            
            // Check for duplicates by both href and asin
            const isDuplicate = processedHrefs.has(href) || 
                               (asin && processedAsins.has(asin));
            
            if (!isDuplicate) {
                processedHrefs.add(href);
                if (asin) processedAsins.add(asin);
                
                links.push({
                    href: href,
                    title: title,
                    index: index,
                    asin: asin,
                    method: 'standard'
                });
            }
        }
    });
    
    // Method 2: Sponsored products (they might have different structure)
    const sponsoredProducts = document.querySelectorAll('[data-component-type="s-sponsor"]');
    console.log('Sponsored products found:', sponsoredProducts.length);
    
    sponsoredProducts.forEach((product, index) => {
        const asin = product.getAttribute('data-asin');
        
        let link = product.querySelector('h2 a');
        if (!link) link = product.querySelector('a[href*="/dp/"]');
        if (!link) link = product.querySelector('a[href*="/-/en/"]');
        
        if (link) {
            const href = link.getAttribute('href');
            const title = link.textContent?.trim() || 'No title';
            
            if (href && !processedHrefs.has(href) && 
                !(asin && processedAsins.has(asin))) {
                processedHrefs.add(href);
                if (asin) processedAsins.add(asin);
                
                links.push({
                    href: href,
                    title: title,
                    index: index,
                    asin: asin,
                    method: 'sponsored'
                });
            }
        }
    });
    
    // Method 3: Any product with data-asin (backup method)
    const allProducts = document.querySelectorAll('[data-asin]');
    allProducts.forEach((product, index) => {
        const asin = product.getAttribute('data-asin');
        
        if (asin && processedAsins.has(asin)) {
            return;
        }
        
        let link = product.querySelector('h2 a');
        if (!link) link = product.querySelector('a[href*="/dp/"]');
        if (!link) link = product.querySelector('a[href*="/-/en/"]');
        
        if (link) {
            const href = link.getAttribute('href');
            const title = link.textContent?.trim() || 'No title';
            
            if (href && !processedHrefs.has(href)) {
                processedHrefs.add(href);
                if (asin) processedAsins.add(asin);
                
                links.push({
                    href: href,
                    title: title,
                    index: index,
                    asin: asin,
                    method: 'data-asin'
                });
            }
        }
    });
    
    // Filter out non-product links
    const filteredLinks = links.filter(link => {
        const href = link.href;
        const title = link.title.toLowerCase();
        
        return href && 
               (href.includes('/dp/') || href.includes('/-/en/') || href.includes('/gp/product/')) &&
               !title.includes('learn about') &&
               !title.includes('visit the help') &&
               !title.includes('advertisement') &&
               title.length > 5;
    });
    
    console.log('Total unique products found:', filteredLinks.length);
    return filteredLinks;
}
"""

# JavaScript code to get seller information from product page
GET_SELLER_INFO_SCRIPT = """
() => {
    let seller = 'Unknown';
    const sellerElement = document.querySelector('#merchantInfoFeature_feature_div .offer-display-feature-text-message');
    if (sellerElement) {
        seller = sellerElement.textContent.trim();
    }
    return { seller: seller };
}
"""

# JavaScript code to extract seller details from seller page
GET_SELLER_DETAILS_SCRIPT = """
() => {
    const allData = {};
    
    const boldSpans = document.querySelectorAll('span.a-text-bold');
    boldSpans.forEach(span => {
        const label = span.textContent?.trim();
        const nextSpan = span.nextElementSibling;
        
        if (label && nextSpan) {
            const value = nextSpan.textContent?.trim();
            if (value && value !== '') {
                allData[label] = value;
            }
        }
    });
    
    let businessName = 'N/A';
    let phoneNumber = 'N/A';
    let email = 'N/A';
    let country = 'N/A';
    
    for (const [label, value] of Object.entries(allData)) {
        if (label.toLowerCase().includes('name') || 
            label.toLowerCase().includes('nom') || 
            label.toLowerCase().includes('nombre') || 
            label.toLowerCase().includes('nome') || 
            label.toLowerCase().includes('firma') || 
            label.toLowerCase().includes('entreprise') || 
            label.toLowerCase().includes('empresa') || 
            label.toLowerCase().includes('azienda') || 
            label.toLowerCase().includes('företag') || 
            label.toLowerCase().includes('nazwa')) {
            businessName = value;
            break;
        }
    }
    
    for (const [label, value] of Object.entries(allData)) {
        if (label.toLowerCase().includes('phone') || 
            label.toLowerCase().includes('telephone') || 
            label.toLowerCase().includes('téléphone') || 
            label.toLowerCase().includes('teléfono') || 
            label.toLowerCase().includes('telefono') || 
            label.toLowerCase().includes('telefon') || 
            label.toLowerCase().includes('numer') || 
            label.toLowerCase().includes('nummer')) {
            phoneNumber = value;
            break;
        }
    }
    
    for (const [label, value] of Object.entries(allData)) {
        if (label.toLowerCase().includes('email') || 
            label.toLowerCase().includes('e-mail') || 
            label.toLowerCase().includes('courriel') || 
            label.toLowerCase().includes('correo') || 
            label.toLowerCase().includes('e-post') || 
            label.toLowerCase().includes('adres') || 
            label.toLowerCase().includes('adresse')) {
            email = value;
            break;
        }
    }
    
    const addressElements = document.querySelectorAll('.indent-left span');
    for (let element of addressElements) {
        const text = element.textContent?.trim();
        if (text && text.length === 2 && /^[A-Z]{2}$/.test(text)) {
            country = text;
            break;
        }
    }
    
    // Extract seller name from h1 element
    let sellerName = 'N/A';
    const sellerNameElement = document.querySelector('h1#seller-name');
    if (sellerNameElement) {
        sellerName = sellerNameElement.textContent.trim();
    }
    
    return {
        business_name: businessName,
        phone_number: phoneNumber,
        email: email,
        country: country,
        seller_name: sellerName
    };
}
"""

# JavaScript code to detect total pages from pagination
GET_TOTAL_PAGES_SCRIPT = """
() => {
    const currentPageSpan = document.querySelector('.s-pagination-item.s-pagination-disabled');
    if (currentPageSpan) {
        const pageNum = parseInt(currentPageSpan.textContent);
        if (!isNaN(pageNum) && pageNum > 1) {
            return pageNum;
        }
    }
    
    const pagination = document.querySelector('.s-pagination-container');
    if (pagination) {
        const pageElements = pagination.querySelectorAll('.s-pagination-item');
        let maxPage = 1;
        pageElements.forEach(element => {
            const text = element.textContent?.trim();
            const num = parseInt(text);
            if (!isNaN(num) && num > maxPage) {
                maxPage = num;
            }
        });
        return maxPage;
    }
    
    return 1;
}
"""

# JavaScript code to check if there's a next page
HAS_NEXT_PAGE_SCRIPT = """
() => {
    const nextButton = document.querySelector('.s-pagination-next:not(.s-pagination-disabled)');
    if (nextButton && nextButton.getAttribute('aria-disabled') !== 'true') {
        return true;
    }
    return false;
}
"""

