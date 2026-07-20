import type { Metadata, Viewport } from "next";
import { Fraunces, Inter, Space_Mono, Geist } from "next/font/google";
import "./globals.css";
import seoConfig from "@/config/seo.config";
import StructuredData from "@/components/StructuredData";
import Analytics from "@/components/Analytics";
import Providers from "./providers";
import { cn } from "@/lib/utils";

const geist = Geist({subsets:['latin'],variable:'--font-sans'});


// "Field Instrument" type system: an optical serif for display, a neutral body, and a
// monospace for data / instrument-readout labels.
const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  display: "swap",
  axes: ["opsz", "SOFT"],
});

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const spaceMono = Space_Mono({
  variable: "--font-space-mono",
  weight: ["400", "700"],
  subsets: ["latin"],
  display: "swap",
});

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
  userScalable: true,
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#3f7d53' },
    { media: '(prefers-color-scheme: dark)', color: '#21503b' },
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
    <html lang={seoConfig.locale} className={cn("font-sans", geist.variable)}>
      <head>
        <StructuredData />
        <link rel="canonical" href={seoConfig.siteUrl} />
        <link rel="alternate" hrefLang="en" href={seoConfig.siteUrl} />
        <link rel="alternate" hrefLang="x-default" href={seoConfig.siteUrl} />
      </head>
      <body
        className={`${fraunces.variable} ${inter.variable} ${spaceMono.variable} antialiased`}
      >
        <Analytics />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
