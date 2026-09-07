# Proactive Recommendation Bank — Archetype-Conditioned Enhancements

This file specifies proactive suggestions to enhance AI discoverability when no fatal defect
was detected. They are conditioned on the site's archetype and are strictly omitted if
a corresponding finding already flagged an issue for that topic.

---

## Ecommerce

### `ecommerce_return_policy_schema`
- **Topic**: `return_refund`
- **Archetype**: `ecommerce`
- **Title**: Add Schema.org `MerchantReturnPolicy` Structured Markup
- **Description**:
  While your site provides return policy text, adding structured `MerchantReturnPolicy` schema linked
  via `hasMerchantReturnPolicy` enables Google Shopping, AI buying assistants, and conversational search
  to quote exact refund windows and return shipping fees directly to shoppers.
- **Priority**: `medium`
- **Code Snippet**:
  ```json
  {
    "@context": "https://schema.org",
    "@type": "MerchantReturnPolicy",
    "applicableCountry": "US",
    "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
    "merchantReturnDays": "<actual_return_days_e.g._30>",
    "returnMethod": "https://schema.org/ReturnByMail",
    "returnFees": "https://schema.org/FreeReturn"
  }
  ```

### `ecommerce_shipping_details`
- **Topic**: `shipping_policy`
- **Archetype**: `ecommerce`
- **Title**: Declare Structured `OfferShippingDetails` on Products
- **Description**:
  Add `shippingDetails` to your `Offer` schemas to specify standard delivery transit times and delivery rates.
  This allows AI agents to compare delivery speed when answering buyer inquiries.
- **Priority**: `medium`
- **Code Snippet**:
  ```json
  {
    "@type": "OfferShippingDetails",
    "shippingRate": { "@type": "MonetaryAmount", "value": "<shipping_rate>", "currency": "<currency_code>" },
    "deliveryTime": {
      "@type": "ShippingDeliveryTime",
      "transitTime": { "@type": "QuantitativeValue", "minValue": "<min_days>", "maxValue": "<max_days>", "unitCode": "d" }
    }
  }
  ```

---

## SaaS

### `saas_llms_txt`
- **Topic**: `llms_txt`
- **Archetype**: `saas`
- **Title**: Deploy an `/llms.txt` Machine-Readable Context File
- **Description**:
  Deploy a standard `/llms.txt` file at your domain root. An `/llms.txt` file gives AI assistants,
  code generation models, and agents a concise, authoritative summary of your product capabilities,
  documentation structure, API endpoints, and core pricing plans.
- **Priority**: `medium`
- **Code Snippet**:
  ```markdown
  # Title: <Product Name> API
  > <Concise description of product value proposition and capabilities.>

  ## Documentation
  - [API Quickstart](/docs/quickstart): 5-minute setup guide
  - [CLI Reference](/docs/cli): Command-line tools
  ```

### `saas_software_application_schema`
- **Topic**: `product_overview`
- **Archetype**: `saas`
- **Title**: Markup Landing Pages with `SoftwareApplication` Schema
- **Description**:
  Include `SoftwareApplication` schema detailing `applicationCategory`, `operatingSystem`, and
  `featureList`. This provides explicit machine-readable metadata about your platform's capabilities.
- **Priority**: `low`
- **Code Snippet**:
  ```json
  {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "name": "<Product Name>",
    "applicationCategory": "BusinessApplication",
    "operatingSystem": "All",
    "offers": { "@type": "Offer", "price": "<tier_price>", "priceCurrency": "<currency_code>" }
  }
  ```

---

## Documentation (Docs)

### `docs_llms_txt_endpoints`
- **Topic**: `llms_txt`
- **Archetype**: `docs`
- **Title**: Provide Curated Markdown Endpoints for AI Dev Tools
- **Description**:
  Provide an `/llms.txt` index linking to clean raw markdown versions of all tutorials and API guides.
  Cursor, Copilot, and other agentic coding tools utilize `/llms.txt` to inject accurate documentation context.
- **Priority**: `medium`
- **Code Snippet**:
  ```markdown
  # Docs Index for LLMs
  - [Installation Guide](/docs/install.md): Core setup
  - [API Reference](/docs/api.md): Full endpoints
  ```

### `docs_copyable_code_blocks`
- **Topic**: `installation`
- **Archetype**: `docs`
- **Title**: Ensure Every Code Block Has Explicit Language Identifiers
- **Description**:
  Tag all `<pre><code>` blocks with clean language classes (e.g. `class="language-bash"` or `class="language-python"`).
  AI scrapers use language attributes to reliably extract executable code snippets without ambiguity.
- **Priority**: `low`
- **Code Snippet**:
  ```html
  <pre><code class="language-bash">npm install <package-name></code></pre>
  ```

---

## News & Content

### `news_author_person_schema`
- **Topic**: `authorship`
- **Archetype**: `news`
- **Title**: Enrich Article Authors with `Person` Schema and `sameAs` Links
- **Description**:
  Enhance author bylines with structured `Person` entities containing `sameAs` links to verified author profiles
  (LinkedIn, Muck Rack, X, Wikipedia). This helps LLMs verify authority and authoritativeness (E-E-A-T).
- **Priority**: `medium`
- **Code Snippet**:
  ```json
  {
    "@type": "Person",
    "name": "<author_name>",
    "jobTitle": "Investigative Reporter",
    "sameAs": ["https://twitter.com/<handle>", "https://muckrack.com/<handle>"]
  }
  ```

---

## Local Business

### `local_geo_and_hours`
- **Topic**: `business_hours`
- **Archetype**: `local_business`
- **Title**: Add Detailed `OpeningHoursSpecification` and `GeoCoordinates`
- **Description**:
  Provide explicit ISO day-of-week opening hours and geographic latitude/longitude in your `LocalBusiness` schema
  to enable map-based search assistants to answer "Is this business open right now?" accurately.
- **Priority**: `medium`
- **Code Snippet**:
  ```json
  {
    "@context": "https://schema.org",
    "@type": "LocalBusiness",
    "geo": { "@type": "GeoCoordinates", "latitude": "<business_latitude>", "longitude": "<business_longitude>" },
    "openingHoursSpecification": [{
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
      "opens": "09:00",
      "closes": "17:00"
    }]
  }
  ```

---

## Corporate

### `corporate_organization_identity`
- **Topic**: `commercial_solutions`
- **Archetype**: `corporate`
- **Title**: Implement Canonical `Corporation` Schema with Official Identifiers
- **Description**:
  Declare `Corporation` schema with `legalName`, `taxID` / `leiCode`, and explicit `contactPoint` entries
  for Investor Relations and Media Inquiries. This eliminates identity ambiguity in financial and enterprise AI tools.
- **Priority**: `low`
- **Code Snippet**:
  ```json
  {
    "@context": "https://schema.org",
    "@type": "Corporation",
    "name": "<company_name>",
    "legalName": "<official_legal_entity_name>",
    "contactPoint": {
      "@type": "ContactPoint",
      "contactType": "investor relations",
      "email": "<investor_relations_email>"
    }
  }
  ```
