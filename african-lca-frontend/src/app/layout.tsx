import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import seoConfig from "@/config/seo.config";
import StructuredData from "@/components/StructuredData";
import Analytics from "@/components/Analytics";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
  userScalable: true,
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#10b981' },
    { media: '(prefers-color-scheme: dark)', color: '#059669' },
  ],
};

export const metadata: Metadata = {
  metadataBase: new URL(seoConfig.siteUrl),
  title: {
    default: seoConfig.defaultTitle,
    template: seoConfig.titleTemplate,
  },
  description: seoConfig.defaultDescription,
  keywords: seoConfig.keywords,
  authors: [
    { name: seoConfig.organization.name },
    { name: "Sustainable Agrifood Systems Engineering Lab", url: "https://sasellab.com/" },
    { name: "McGill University", url: "https://www.mcgill.ca/" },
  ],
  creator: "Sustainable Agrifood Systems Engineering Lab",
  publisher: seoConfig.organization.name,
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  openGraph: {
    type: "website",
    locale: seoConfig.locale,
    alternateLocale: seoConfig.alternateLocales,
    url: seoConfig.siteUrl,
    siteName: seoConfig.siteName,
    title: seoConfig.defaultTitle,
    description: seoConfig.defaultDescription,
    images: [
      {
        url: seoConfig.ogImage.url,
        width: seoConfig.ogImage.width,
        height: seoConfig.ogImage.height,
        alt: seoConfig.ogImage.alt,
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    site: seoConfig.social.twitter,
    creator: seoConfig.social.twitter,
    title: seoConfig.defaultTitle,
    description: seoConfig.defaultDescription,
    images: [seoConfig.ogImage.url],
  },
  robots: {
    index: process.env.NODE_ENV === 'production',
    follow: process.env.NODE_ENV === 'production',
    googleBot: {
      index: process.env.NODE_ENV === 'production',
      follow: process.env.NODE_ENV === 'production',
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  alternates: {
    canonical: seoConfig.siteUrl,
  },
  verification: {
    google: process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION,
    yandex: process.env.NEXT_PUBLIC_YANDEX_VERIFICATION,
  },
  category: 'technology',
  classification: 'Environmental Technology, Agricultural Technology, Sustainability',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang={seoConfig.locale}>
      <head>
        <StructuredData />
        <link rel="canonical" href={seoConfig.siteUrl} />
        <link rel="alternate" hrefLang="en" href={seoConfig.siteUrl} />
        <link rel="alternate" hrefLang="en-GH" href={`${seoConfig.siteUrl}?locale=en-GH`} />
        <link rel="alternate" hrefLang="en-NG" href={`${seoConfig.siteUrl}?locale=en-NG`} />
        <meta name="geo.region" content="GH" />
        <meta name="geo.region" content="NG" />
        <meta name="geo.placename" content="Ghana" />
        <meta name="geo.placename" content="Nigeria" />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <Analytics />
        {children}
      </body>
    </html>
  );
}
