/**
 * SEO Configuration for Green Means Go
 * Professional-level SEO setup for production and development
 */

export const seoConfig = {
  // Site Information
  siteName: process.env.NEXT_PUBLIC_SITE_NAME || 'Green Means Go',
  siteUrl: process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000',
  domain: process.env.NEXT_PUBLIC_DOMAIN || 'greenmeansgo.ai',

  // Default Metadata
  defaultTitle: 'Green Means Go - African Food Systems LCA Platform',
  titleTemplate: '%s | Green Means Go',
  defaultDescription: 'Professional Life Cycle Assessment (LCA) platform for African food systems. Assess environmental impact of farms and food processing facilities following ISO 14044 standards. Covering Ghana, Nigeria, and expanding across Africa.',

  // Keywords
  keywords: [
    'LCA',
    'Life Cycle Assessment',
    'African agriculture',
    'sustainability assessment',
    'food systems',
    'environmental impact',
    'carbon footprint',
    'Ghana agriculture',
    'Nigeria agriculture',
    'West Africa',
    'sustainable farming',
    'food processing',
    'ISO 14044',
    'climate smart agriculture',
    'agricultural sustainability',
    'farm assessment',
    'environmental footprint',
    'GHG emissions',
    'water footprint',
    'sustainable food production',
  ],

  // Social Media
  social: {
    twitter: process.env.NEXT_PUBLIC_TWITTER_HANDLE || '@greenmeansgo',
    facebook: process.env.NEXT_PUBLIC_FACEBOOK_PAGE || 'greenmeansgo',
  },

  // Open Graph Default Images
  ogImage: {
    url: '/og-image.png',
    width: 1200,
    height: 630,
    alt: 'Green Means Go - African Food Systems LCA',
  },

  // Structured Data
  organization: {
    name: 'Green Means Go',
    legalName: 'Green Means Go',
    url: process.env.NEXT_PUBLIC_SITE_URL || 'https://greenmeansgo.ai',
    logo: '/logo.svg',
    foundingDate: '2024',
    founders: [
      {
        name: 'Green Means Go Team',
      },
    ],
    address: {
      addressCountry: 'GH',
      addressRegion: 'West Africa',
    },
    contactPoint: {
      contactType: 'Customer Support',
      email: 'contact@greenmeansgo.ai',
    },
    sameAs: [
      // Add social media profiles when available
      'https://twitter.com/greenmeansgo',
      'https://linkedin.com/company/greenmeansgo',
    ],
  },

  // Service Schema
  service: {
    name: 'Life Cycle Assessment Services',
    description: 'Professional LCA services for African food systems',
    provider: 'Green Means Go',
    areaServed: ['Ghana', 'Nigeria', 'West Africa', 'Africa'],
    serviceType: [
      'Environmental Impact Assessment',
      'Life Cycle Assessment',
      'Sustainability Consulting',
      'Agricultural Assessment',
      'Food Processing Assessment',
    ],
  },

  // Analytics
  analytics: {
    googleAnalyticsId: process.env.NEXT_PUBLIC_GA_TRACKING_ID,
    googleTagManagerId: process.env.NEXT_PUBLIC_GTM_ID,
  },

  // Locale
  locale: process.env.NEXT_PUBLIC_DEFAULT_LOCALE || 'en',
  alternateLocales: ['en-GH', 'en-NG'],
};

export default seoConfig;
