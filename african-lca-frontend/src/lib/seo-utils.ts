/**
 * SEO Utility Functions
 * Helper functions for generating page-specific SEO metadata
 */

import { Metadata } from 'next';
import seoConfig from '@/config/seo.config';

interface PageSEOProps {
  title: string;
  description?: string;
  keywords?: string[];
  ogImage?: string;
  noindex?: boolean;
  canonical?: string;
}

/**
 * Generate metadata for a specific page
 */
export function generatePageMetadata({
  title,
  description = seoConfig.defaultDescription,
  keywords = [],
  ogImage = seoConfig.ogImage.url,
  noindex = false,
  canonical,
}: PageSEOProps): Metadata {
  const fullTitle = `${title} | ${seoConfig.siteName}`;
  const pageKeywords = [...seoConfig.keywords, ...keywords];
  const canonicalUrl = canonical || seoConfig.siteUrl;

  return {
    title,
    description,
    keywords: pageKeywords,
    openGraph: {
      title: fullTitle,
      description,
      type: 'website',
      url: canonicalUrl,
      siteName: seoConfig.siteName,
      images: [
        {
          url: ogImage,
          width: seoConfig.ogImage.width,
          height: seoConfig.ogImage.height,
          alt: title,
        },
      ],
    },
    twitter: {
      card: 'summary_large_image',
      title: fullTitle,
      description,
      images: [ogImage],
      site: seoConfig.social.twitter,
      creator: seoConfig.social.twitter,
    },
    robots: noindex
      ? {
          index: false,
          follow: false,
        }
      : undefined,
    alternates: {
      canonical: canonicalUrl,
    },
  };
}

/**
 * Generate breadcrumb items for structured data
 */
export function generateBreadcrumbs(
  items: Array<{ name: string; url: string }>
): Array<{ name: string; url: string }> {
  return [{ name: 'Home', url: '/' }, ...items];
}

/**
 * Format date for structured data
 */
export function formatDateForSchema(date: Date): string {
  return date.toISOString();
}

/**
 * Clean and optimize text for SEO
 */
export function optimizeText(text: string, maxLength: number = 160): string {
  // Remove extra whitespace
  const cleaned = text.replace(/\s+/g, ' ').trim();

  // Truncate if too long
  if (cleaned.length <= maxLength) {
    return cleaned;
  }

  // Find last complete word before limit
  const truncated = cleaned.substring(0, maxLength);
  const lastSpace = truncated.lastIndexOf(' ');

  return lastSpace > 0 ? truncated.substring(0, lastSpace) + '...' : truncated + '...';
}

/**
 * Generate FAQ schema items
 */
export function generateFAQItems(
  faqs: Array<{ question: string; answer: string }>
): Array<{ question: string; answer: string }> {
  return faqs.map((faq) => ({
    question: optimizeText(faq.question, 200),
    answer: optimizeText(faq.answer, 500),
  }));
}

/**
 * Extract keywords from content
 */
export function extractKeywords(content: string, count: number = 10): string[] {
  // Simple keyword extraction (in production, use more sophisticated NLP)
  const words = content
    .toLowerCase()
    .replace(/[^\w\s]/g, '')
    .split(/\s+/)
    .filter((word) => word.length > 3); // Filter out short words

  // Count frequency
  const frequency: Record<string, number> = {};
  words.forEach((word) => {
    frequency[word] = (frequency[word] || 0) + 1;
  });

  // Sort by frequency and return top keywords
  return Object.entries(frequency)
    .sort((a, b) => b[1] - a[1])
    .slice(0, count)
    .map(([word]) => word);
}
