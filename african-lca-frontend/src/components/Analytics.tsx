'use client';

import Script from 'next/script';
import { usePathname, useSearchParams } from 'next/navigation';
import { useEffect } from 'react';
import seoConfig from '@/config/seo.config';

// Extend Window interface to include gtag
declare global {
  interface Window {
    gtag?: (
      command: 'config' | 'event' | 'js' | 'set',
      targetId: string | Date,
      config?: Record<string, unknown>
    ) => void;
    dataLayer?: unknown[];
  }
}

/**
 * Google Analytics Component
 * Only loads in production environment
 */
export function GoogleAnalytics() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const gaId = seoConfig.analytics.googleAnalyticsId;

  useEffect(() => {
    if (!gaId || process.env.NODE_ENV !== 'production') return;

    const url = pathname + searchParams.toString();

    // Track page view
    if (typeof window !== 'undefined' && window.gtag) {
      window.gtag('config', gaId, {
        page_path: url,
      });
    }
  }, [pathname, searchParams, gaId]);

  if (!gaId || process.env.NODE_ENV !== 'production') {
    return null;
  }

  return (
    <>
      <Script
        strategy="afterInteractive"
        src={`https://www.googletagmanager.com/gtag/js?id=${gaId}`}
      />
      <Script
        id="google-analytics"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{
          __html: `
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', '${gaId}', {
              page_path: window.location.pathname,
            });
          `,
        }}
      />
    </>
  );
}

/**
 * Google Tag Manager Component
 * Only loads in production environment
 */
export function GoogleTagManager() {
  const gtmId = seoConfig.analytics.googleTagManagerId;

  if (!gtmId || process.env.NODE_ENV !== 'production') {
    return null;
  }

  return (
    <>
      <Script
        id="google-tag-manager"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{
          __html: `
            (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
            new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
            j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
            'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
            })(window,document,'script','dataLayer','${gtmId}');
          `,
        }}
      />
      <noscript>
        <iframe
          src={`https://www.googletagmanager.com/ns.html?id=${gtmId}`}
          height="0"
          width="0"
          style={{ display: 'none', visibility: 'hidden' }}
        />
      </noscript>
    </>
  );
}

/**
 * Combined Analytics Component
 * Includes both GA and GTM
 */
export default function Analytics() {
  return (
    <>
      <GoogleAnalytics />
      <GoogleTagManager />
    </>
  );
}
