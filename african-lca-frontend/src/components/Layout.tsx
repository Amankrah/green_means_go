'use client';

import React from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { Sprout, Menu, X, BarChart3, Home, Info, Mail } from 'lucide-react';
import { useState } from 'react';
import { motion } from 'framer-motion';

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const navigation = [
    { name: 'Home', href: '/', icon: Home },
    { name: 'Farm Assessment', href: '/assessment', icon: Sprout },
    { name: 'Results', href: '/results', icon: BarChart3 },
    { name: 'About', href: '/about', icon: Info },
    { name: 'Contact', href: '/contact', icon: Mail },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 via-emerald-50 to-teal-50">
      {/* Header - Sticky with Glassmorphism */}
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-lg shadow-lg border-b border-white/20 supports-[backdrop-filter]:bg-white/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            {/* Logo */}
            <Link href="/" className="flex items-center space-x-3 group">
              <Image 
                src="/logo.svg" 
                alt="Green Means Go Logo" 
                width={48} 
                height={48}
                className="transition-transform duration-200 group-hover:scale-105"
              />
              <div className="hidden sm:block">
                <div className="flex items-center gap-2">
                  <h1 className="text-lg sm:text-xl font-bold text-gray-900">Green Means Go</h1>
                  <span className="px-2 py-0.5 text-xs font-semibold text-orange-600 bg-orange-100 rounded-full border border-orange-200">
                    BETA
                  </span>
                </div>
                <p className="text-xs sm:text-sm text-green-600">African Food Systems LCA</p>
              </div>
              <div className="sm:hidden">
                <div className="flex items-center gap-1.5">
                  <h1 className="text-lg font-bold text-gray-900">GMG</h1>
                  <span className="px-1.5 py-0.5 text-[10px] font-semibold text-orange-600 bg-orange-100 rounded-full">
                    BETA
                  </span>
                </div>
                <p className="text-xs text-green-600">Food Systems</p>
              </div>
            </Link>

            {/* Desktop Navigation */}
            <nav className="hidden md:flex space-x-8">
              {navigation.map((item) => (
                <Link
                  key={item.name}
                  href={item.href}
                  className="flex items-center space-x-2 px-3 py-2 rounded-lg text-gray-700 hover:text-green-600 hover:bg-white/50 backdrop-blur-sm transition-all duration-200"
                >
                  <item.icon className="w-5 h-5" />
                  <span className="font-medium">{item.name}</span>
                </Link>
              ))}
            </nav>

            {/* Mobile menu button */}
            <button
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className="md:hidden p-2 rounded-lg text-gray-400 hover:text-gray-500 hover:bg-white/50 backdrop-blur-sm transition-all duration-200"
            >
              {isMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>

          {/* Mobile Navigation */}
          {isMenuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="md:hidden border-t border-white/30 backdrop-blur-lg py-4"
            >
              <nav className="space-y-2">
                {navigation.map((item) => (
                  <Link
                    key={item.name}
                    href={item.href}
                    className="flex items-center space-x-3 px-3 py-2 rounded-lg text-gray-700 hover:text-green-600 hover:bg-white/50 backdrop-blur-sm transition-all duration-200"
                    onClick={() => setIsMenuOpen(false)}
                  >
                    <item.icon className="w-5 h-5" />
                    <span className="font-medium">{item.name}</span>
                  </Link>
                ))}
              </nav>
            </motion.div>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center">
            <div className="flex items-center justify-center space-x-3 mb-4">
              <Image 
                src="/logo.svg" 
                alt="Green Means Go Logo" 
                width={40} 
                height={40}
              />
              <span className="text-lg font-semibold text-gray-900">Green Means Go</span>
            </div>
            <p className="text-gray-600 mb-2">
              Sustainable food systems assessment for Africa
            </p>
            <p className="text-sm text-gray-500">
              From farm production to food processing - ISO 14044 compliant LCA
            </p>
            <div className="mt-6 flex flex-col sm:flex-row justify-center items-center space-y-2 sm:space-y-0 sm:space-x-6">
              <span className="text-sm text-gray-400">🌾 Ghana</span>
              <span className="text-sm text-gray-400">🌿 Nigeria</span>
              <span className="text-sm text-gray-400 text-center">🌱 More countries coming soon</span>
            </div>
            
            {/* SASEL Lab Credit */}
            <div className="mt-8 pt-6 border-t border-gray-200">
              <p className="text-sm text-gray-600">
                Developed at{' '}
                <a 
                  href="https://sasellab.com/" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="font-semibold text-green-600 hover:text-green-700 transition-colors duration-200 underline decoration-green-300 hover:decoration-green-500"
                >
                  Sustainable Agrifood Systems Engineering Lab
                </a>
                {' '}@ McGill University
              </p>
              <p className="text-xs text-gray-500 mt-2">
                © {new Date().getFullYear()} Green Means Go. All rights reserved.
              </p>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}