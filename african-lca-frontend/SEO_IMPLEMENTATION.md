# SEO Implementation Guide - Green Means Go

## Overview

Professional-level SEO implementation for **greenmeansgo.ai** - ready for both development and production environments.

## Domain Configuration

- **Production Domain**: `https://greenmeansgo.ai`
- **Development**: `http://localhost:3000`
- **API Endpoint**: Configurable via environment variables

## Environment Setup

### Development (.env.local)
```bash
NEXT_PUBLIC_SITE_URL=http://localhost:3000
NEXT_PUBLIC_DOMAIN=greenmeansgo.ai
NEXT_PUBLIC_API_URL=http://localhost:8000
NODE_ENV=development
```

### Production (.env.production)
```bash
NEXT_PUBLIC_SITE_URL=https://greenmeansgo.ai
NEXT_PUBLIC_DOMAIN=greenmeansgo.ai
NEXT_PUBLIC_API_URL=https://api.greenmeansgo.ai
NEXT_PUBLIC_GA_TRACKING_ID=G-XXXXXXXXXX
NEXT_PUBLIC_GTM_ID=GTM-XXXXXXX
NODE_ENV=production
```

## SEO Features Implemented

### 1. Metadata & OpenGraph Tags ✅
- Dynamic title templates
- Comprehensive meta descriptions
- OpenGraph tags for social sharing
- Twitter Card support
- Keywords optimization

### 2. Structured Data (JSON-LD) ✅
- **Organization Schema**: Company information
- **Service Schema**: LCA services offered
- **Website Schema**: Site search capabilities
- **SoftwareApplication Schema**: Platform features
- **FAQ Schema**: Common questions (ready to use)
- **Breadcrumb Schema**: Navigation tracking

### 3. Technical SEO ✅
- **Canonical URLs**: Prevent duplicate content
- **Robots.txt**: Search engine crawling rules
- **Sitemap.xml**: Dynamic sitemap generation
- **Hreflang Tags**: Multi-locale support (Ghana, Nigeria)
- **Geo-targeting**: Regional meta tags

### 4. Analytics & Tracking ✅
- Google Analytics 4 (GA4) integration
- Google Tag Manager (GTM) support
- Environment-aware loading (production only)
- Page view tracking
- Event tracking ready

### 5. Performance Optimization ✅
- Font display: swap for better performance
- Lazy loading analytics scripts
- Viewport configuration
- Theme color for PWA

## File Structure

```
src/
├── config/
│   └── seo.config.ts          # Central SEO configuration
├── components/
│   ├── StructuredData.tsx     # JSON-LD schemas
│   └── Analytics.tsx          # GA4 & GTM integration
├── app/
│   ├── layout.tsx            # Root layout with SEO
│   ├── sitemap.ts            # Dynamic sitemap
│   ├── icon.tsx              # Favicon generator
│   └── apple-icon.tsx        # iOS icon generator
public/
└── robots.txt                # Crawler instructions
```

## Configuration

### SEO Config (`src/config/seo.config.ts`)

Central configuration file containing:
- Site metadata
- Keywords (20+ relevant terms)
- Social media handles
- Organization details
- Service descriptions
- Analytics IDs

### Customization

Edit `seo.config.ts` to update:
```typescript
export const seoConfig = {
  siteName: 'Green Means Go',
  defaultTitle: 'Your custom title',
  defaultDescription: 'Your description',
  keywords: ['keyword1', 'keyword2'],
  // ... more settings
};
```

## Search Engine Optimization Strategy

### Target Keywords

Primary keywords optimized:
- Life Cycle Assessment (LCA)
- African agriculture sustainability
- Environmental impact assessment
- Food systems LCA
- ISO 14044 compliance
- Ghana/Nigeria agriculture

### Content Optimization

Each page includes:
1. Unique title and description
2. Proper heading hierarchy (H1, H2, H3)
3. Alt text for images
4. Semantic HTML structure
5. Internal linking

### Local SEO

Targeted for:
- Ghana (GH)
- Nigeria (NG)
- West Africa region
- English language variants (en-GH, en-NG)

## Analytics Setup

### Google Analytics 4

1. Create GA4 property at [analytics.google.com](https://analytics.google.com)
2. Get tracking ID (G-XXXXXXXXXX)
3. Add to `.env.production`:
   ```bash
   NEXT_PUBLIC_GA_TRACKING_ID=G-XXXXXXXXXX
   ```

### Google Tag Manager

1. Create GTM container at [tagmanager.google.com](https://tagmanager.google.com)
2. Get container ID (GTM-XXXXXXX)
3. Add to `.env.production`:
   ```bash
   NEXT_PUBLIC_GTM_ID=GTM-XXXXXXX
   ```

## Verification

### Google Search Console

1. Go to [search.google.com/search-console](https://search.google.com/search-console)
2. Add property for `greenmeansgo.ai`
3. Verify ownership (recommended: DNS TXT record)
4. Submit sitemap: `https://greenmeansgo.ai/sitemap.xml`

Add verification code to `.env.production`:
```bash
NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION=your_verification_code
```

### Bing Webmaster Tools

1. Go to [bing.com/webmasters](https://www.bing.com/webmasters)
2. Add site
3. Verify and submit sitemap

## robots.txt Rules

```
User-agent: *
Allow: /
Disallow: /api/
Disallow: /_next/
Disallow: /admin/
Sitemap: https://greenmeansgo.ai/sitemap.xml
```

Development automatically blocks crawlers via metadata.

## Sitemap

Dynamic sitemap automatically includes:
- Homepage (priority: 1.0)
- Farm Assessment (priority: 0.9)
- Results (priority: 0.8)
- Processing Assessment (priority: 0.7)

Updates automatically as new pages are added.

## Social Media Integration

### Twitter/X Card

When shared on Twitter:
- Large image card
- Proper title and description
- @greenmeansgo attribution

### Facebook/LinkedIn

When shared on Facebook/LinkedIn:
- OpenGraph image (1200x630px)
- Rich preview with title/description
- Proper site attribution

## Performance Monitoring

Track these SEO metrics:
1. **Organic traffic** - GA4
2. **Search rankings** - Google Search Console
3. **Page speed** - PageSpeed Insights
4. **Core Web Vitals** - Search Console
5. **Click-through rate** - Search Console

## Best Practices Implemented

✅ Semantic HTML5 structure
✅ Mobile-first responsive design
✅ Fast page load times
✅ HTTPS (production)
✅ Clean URL structure
✅ Proper heading hierarchy
✅ Alt text for images
✅ Internal linking
✅ External link attribution
✅ Structured data markup
✅ XML sitemap
✅ Robots.txt
✅ Canonical URLs
✅ Social media meta tags
✅ Analytics tracking
✅ Performance optimization

## Deployment Checklist

Before going to production:

- [ ] Update `.env.production` with real values
- [ ] Add Google Analytics tracking ID
- [ ] Add Google Tag Manager ID
- [ ] Verify Search Console ownership
- [ ] Submit sitemap to Search Console
- [ ] Submit sitemap to Bing Webmaster
- [ ] Create social media profiles
- [ ] Create OpenGraph image (1200x630px)
- [ ] Test all meta tags with [metatags.io](https://metatags.io)
- [ ] Run Lighthouse audit
- [ ] Check mobile-friendliness
- [ ] Verify structured data with [schema.org validator](https://validator.schema.org)

## Testing Tools

Use these tools to verify SEO:

1. **Meta Tags**: [metatags.io](https://metatags.io)
2. **Structured Data**: [Google Rich Results Test](https://search.google.com/test/rich-results)
3. **Mobile-Friendly**: [Google Mobile-Friendly Test](https://search.google.com/test/mobile-friendly)
4. **Page Speed**: [PageSpeed Insights](https://pagespeed.web.dev)
5. **Schema Validator**: [Schema.org Validator](https://validator.schema.org)

## Maintenance

Regular SEO tasks:

- **Weekly**: Monitor Search Console for errors
- **Monthly**: Review analytics and rankings
- **Quarterly**: Update keywords and content
- **Annually**: Comprehensive SEO audit

## Support & Resources

- Next.js SEO Docs: [nextjs.org/docs/app/building-your-application/optimizing](https://nextjs.org/docs/app/building-your-application/optimizing)
- Schema.org: [schema.org](https://schema.org)
- Google Search Central: [developers.google.com/search](https://developers.google.com/search)

---

**Last Updated**: November 2025
**Platform**: Green Means Go - greenmeansgo.ai
**Framework**: Next.js 15 App Router

📊 Next Steps for Production:
Get Analytics IDs:
NEXT_PUBLIC_GA_TRACKING_ID=G-XXXXXXXXXX
NEXT_PUBLIC_GTM_ID=GTM-XXXXXXX
Verify Search Console:
Add property at search.google.com
Submit sitemap: https://greenmeansgo.ai/sitemap.xml
Create Social Media:
Twitter: @greenmeansgo
LinkedIn company page
Facebook page
Create OG Image:
1200x630px image for social sharing
Place in /public/og-image.png