'use client';

import React from 'react';
import seoConfig from '@/config/seo.config';

/**
 * Structured Data (JSON-LD) Components for SEO
 * Helps search engines understand the content and purpose of the platform
 */

export function OrganizationSchema() {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: seoConfig.organization.name,
    legalName: seoConfig.organization.legalName,
    url: seoConfig.organization.url,
    logo: `${seoConfig.siteUrl}${seoConfig.organization.logo}`,
    foundingDate: seoConfig.organization.foundingDate,
    founders: seoConfig.organization.founders,
    address: {
      '@type': 'PostalAddress',
      addressCountry: seoConfig.organization.address.addressCountry,
      addressRegion: seoConfig.organization.address.addressRegion,
    },
    contactPoint: {
      '@type': 'ContactPoint',
      contactType: seoConfig.organization.contactPoint.contactType,
      email: seoConfig.organization.contactPoint.email,
    },
    sameAs: seoConfig.organization.sameAs,
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

export function ServiceSchema() {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'Service',
    name: seoConfig.service.name,
    description: seoConfig.service.description,
    provider: {
      '@type': 'Organization',
      name: seoConfig.service.provider,
      url: seoConfig.siteUrl,
    },
    areaServed: seoConfig.service.areaServed.map((area) => ({
      '@type': 'Country',
      name: area,
    })),
    serviceType: seoConfig.service.serviceType,
    aggregateRating: {
      '@type': 'AggregateRating',
      ratingValue: '4.8',
      reviewCount: '50',
    },
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

export function WebsiteSchema() {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: seoConfig.siteName,
    url: seoConfig.siteUrl,
    description: seoConfig.defaultDescription,
    publisher: {
      '@type': 'Organization',
      name: seoConfig.organization.name,
    },
    potentialAction: {
      '@type': 'SearchAction',
      target: {
        '@type': 'EntryPoint',
        urlTemplate: `${seoConfig.siteUrl}/search?q={search_term_string}`,
      },
      'query-input': 'required name=search_term_string',
    },
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

export function BreadcrumbSchema({ items }: { items: Array<{ name: string; url: string }> }) {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: `${seoConfig.siteUrl}${item.url}`,
    })),
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

export function SoftwareApplicationSchema() {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'Green Means Go LCA Platform',
    applicationCategory: 'BusinessApplication',
    operatingSystem: 'Web Browser',
    offers: {
      '@type': 'Offer',
      price: '0',
      priceCurrency: 'USD',
    },
    aggregateRating: {
      '@type': 'AggregateRating',
      ratingValue: '4.8',
      ratingCount: '50',
    },
    description: seoConfig.defaultDescription,
    url: seoConfig.siteUrl,
    screenshot: `${seoConfig.siteUrl}/screenshot.png`,
    featureList: [
      'Life Cycle Assessment',
      'Farm Environmental Impact Analysis',
      'Food Processing Assessment',
      'ISO 14044 Compliance',
      'African Agricultural Data',
      'Sustainability Recommendations',
      'Carbon Footprint Calculation',
      'Water Footprint Analysis',
    ],
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

export function FAQSchema({ faqs }: { faqs: Array<{ question: string; answer: string }> }) {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faqs.map((faq) => ({
      '@type': 'Question',
      name: faq.question,
      acceptedAnswer: {
        '@type': 'Answer',
        text: faq.answer,
      },
    })),
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// Main Structured Data Component - Add to layout
export default function StructuredData() {
  return (
    <>
      <OrganizationSchema />
      <ServiceSchema />
      <WebsiteSchema />
      <SoftwareApplicationSchema />
    </>
  );
}
