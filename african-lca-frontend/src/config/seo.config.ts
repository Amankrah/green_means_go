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
  defaultTitle: 'Green Means Go - Global Food Systems LCA Platform',
  titleTemplate: '%s | Green Means Go',
  defaultDescription: 'Life Cycle Assessment (LCA) platform for food systems worldwide. Developed at the Sustainable Agrifood Systems Engineering Lab at McGill University. Assess the environmental impact of farms and food processing facilities following ISO 14040/14044 standards — demonstrated with Canada and onboarding countries across the globe.',

  // Keywords
  keywords: [
    'LCA',
    'Life Cycle Assessment',
    'sustainability assessment',
    'food systems',
    'environmental impact',
    'carbon footprint',
    'sustainable farming',
    'food processing',
    'ISO 14044',
    'ISO 14040',
    'climate smart agriculture',
    'agricultural sustainability',
    'farm assessment',
    'environmental footprint',
    'GHG emissions',
    'water footprint',
    'sustainable food production',
    'Canada agriculture',
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
    alt: 'Green Means Go - Global Food Systems LCA',
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
        name: 'Sustainable Agrifood Systems Engineering Lab',
        url: 'https://sasellab.com/',
      },
    ],
    parentOrganization: {
      name: 'Sustainable Agrifood Systems Engineering Lab',
      url: 'https://sasellab.com/',
      alternateName: 'SASEL Lab',
      parentOrganization: {
        name: 'McGill University',
        url: 'https://www.mcgill.ca/',
      },
    },
    address: {
      addressCountry: 'CA',
      addressRegion: 'Quebec',
      addressLocality: 'Sainte-Anne-de-Bellevue',
      postalCode: 'H9X 3V9',
      streetAddress: '2111 Lakeshore Road',
    },
    contactPoint: {
      contactType: 'Customer Support',
      email: 'ebenezer.kwofie@mcgill.ca',
      telephone: '+1-514-398-7776',
    },
    sameAs: [
      // Add social media profiles when available
      'https://sasellab.com/',
      'https://twitter.com/greenmeansgo',
      'https://linkedin.com/company/greenmeansgo',
    ],
  },

  // Service Schema
  service: {
    name: 'Life Cycle Assessment Services',
    description: 'Professional LCA services for food systems worldwide',
    provider: 'Green Means Go',
    areaServed: ['Canada', 'Ghana', 'Nigeria', 'Worldwide'],
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
  alternateLocales: ['en-CA'],
};

export default seoConfig;
