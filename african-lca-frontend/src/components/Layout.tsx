'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname, useRouter } from 'next/navigation';
import {
  ArrowUpRight,
  BarChart3,
  ChevronDown,
  Home,
  Info,
  LayoutDashboard,
  LogOut,
  Mail,
  Menu,
  Sprout,
  X,
} from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { useAuth } from '@/contexts/AuthContext';

interface LayoutProps {
  children: React.ReactNode;
}

const ROLE_LABEL: Record<string, string> = {
  farmer: 'Farmer',
  extension_officer: 'Extension officer',
  processor: 'Processor',
};

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] || '') + (parts[1]?.[0] || '')).toUpperCase() || 'U';
}

export default function Layout({ children }: LayoutProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const { user, isAuthenticated, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    setIsMenuOpen(false);
    setUserMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsMenuOpen(false);
        setUserMenuOpen(false);
      }
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, []);

  const handleSignOut = async () => {
    setUserMenuOpen(false);
    setIsMenuOpen(false);
    await logout();
    router.push('/');
  };

  const navigation = [
    { name: 'Home', href: '/', icon: Home },
    ...(isAuthenticated ? [{ name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard }] : []),
    { name: 'Assessment', href: '/assessment', icon: Sprout },
    { name: 'Results', href: '/results', icon: BarChart3 },
    { name: 'About', href: '/about', icon: Info },
    { name: 'Contact', href: '/contact', icon: Mail },
  ];

  const isActive = (href: string) =>
    href === '/' ? pathname === '/' : pathname === href || pathname.startsWith(`${href}/`);

  const accountMenuAria: React.AriaAttributes = {
    'aria-expanded': userMenuOpen,
    'aria-controls': 'account-menu',
  };
  const mobileMenuAria: React.AriaAttributes = {
    'aria-expanded': isMenuOpen,
    'aria-controls': 'mobile-navigation',
  };

  return (
    <div className="flex min-h-screen flex-col bg-paper">
      <header className="sticky top-0 z-50 border-b border-line bg-paper/92 backdrop-blur-xl supports-[backdrop-filter]:bg-paper/80">
        <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-8">
          <div className="flex h-[76px] items-center justify-between gap-5">
            <Link href="/" className="group flex shrink-0 items-center gap-3" aria-label="Green Means Go home">
              <span className="relative grid h-11 w-11 place-items-center overflow-hidden rounded-full bg-spruce">
                <Image
                  src="/logo.svg"
                  alt=""
                  width={44}
                  height={44}
                  className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                />
              </span>
              <div>
                <span className="font-display text-xl font-medium leading-none text-ink">Green Means Go</span>
                <span className="mt-1 hidden font-mono text-[0.56rem] uppercase tracking-[0.15em] text-muted sm:block">
                  Food-system life-cycle assessment
                </span>
              </div>
            </Link>

            <div className="hidden items-center gap-5 lg:flex">
              <nav className="flex items-center" aria-label="Primary navigation">
                {navigation.map((item) => (
                  <Link
                    key={item.name}
                    href={item.href}
                    aria-current={isActive(item.href) ? 'page' : undefined}
                    className={`relative px-3 py-2 text-sm font-medium transition-colors ${
                      isActive(item.href) ? 'text-spruce' : 'text-muted hover:text-ink'
                    }`}
                  >
                    {item.name}
                    {isActive(item.href) && (
                      <motion.span
                        layoutId="active-navigation"
                        className="absolute inset-x-3 -bottom-[21px] h-0.5 bg-moss"
                      />
                    )}
                  </Link>
                ))}
              </nav>

              <span className="h-7 w-px bg-line" aria-hidden="true" />

              {isAuthenticated && user ? (
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setUserMenuOpen((value) => !value)}
                    aria-label="Open account menu"
                    aria-haspopup="menu"
                    {...accountMenuAria}
                    className="flex items-center gap-2 rounded-full p-1 pr-2 transition-colors hover:bg-surface"
                  >
                    <span className="grid h-9 w-9 place-items-center rounded-full bg-spruce text-sm font-semibold text-paper">
                      {initials(user.full_name)}
                    </span>
                    <ChevronDown className={`h-4 w-4 text-muted transition-transform ${userMenuOpen ? 'rotate-180' : ''}`} />
                  </button>
                  <AnimatePresence>
                    {userMenuOpen && (
                      <motion.div
                        id="account-menu"
                        initial={{ opacity: 0, y: -6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        className="absolute right-0 mt-3 w-64 overflow-hidden rounded-2xl border border-line bg-surface shadow-[0_20px_55px_-25px_rgba(16,41,31,0.55)]"
                      >
                        <div className="border-b border-line px-4 py-4">
                          <p className="truncate font-medium text-ink">{user.full_name}</p>
                          <p className="mt-0.5 truncate text-xs text-muted">{user.email}</p>
                          <p className="mt-2 font-mono text-[0.58rem] uppercase tracking-wider text-moss">{ROLE_LABEL[user.role]}</p>
                        </div>
                        <Link href="/dashboard" className="flex items-center gap-2 px-4 py-3 text-sm text-ink hover:bg-paper">
                          <LayoutDashboard className="h-4 w-4" /> Dashboard
                        </Link>
                        <button type="button" onClick={handleSignOut} className="flex w-full items-center gap-2 px-4 py-3 text-sm text-ink hover:bg-paper">
                          <LogOut className="h-4 w-4" /> Sign out
                        </button>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Link href="/login" className="rounded-full px-4 py-2 text-sm font-medium text-ink hover:bg-surface">Sign in</Link>
                  <Link href="/signup" className="rounded-full bg-spruce px-5 py-2.5 text-sm font-medium text-paper transition-colors hover:bg-ink">Start assessment</Link>
                </div>
              )}
            </div>

            <button
              type="button"
              onClick={() => setIsMenuOpen((value) => !value)}
              aria-label={isMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
              {...mobileMenuAria}
              className="rounded-full border border-line p-2.5 text-ink hover:bg-surface lg:hidden"
            >
              {isMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>

          <AnimatePresence>
            {isMenuOpen && (
              <motion.div
                id="mobile-navigation"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden lg:hidden"
              >
                <nav className="border-t border-line py-4" aria-label="Mobile navigation">
                  {navigation.map((item) => (
                    <Link
                      key={item.name}
                      href={item.href}
                      aria-current={isActive(item.href) ? 'page' : undefined}
                      className={`flex items-center gap-3 rounded-xl px-3 py-3 font-medium ${
                        isActive(item.href) ? 'bg-surface text-spruce' : 'text-ink hover:bg-surface'
                      }`}
                    >
                      <item.icon className="h-5 w-5" />
                      {item.name}
                    </Link>
                  ))}
                  <div className="mt-4 border-t border-line pt-4">
                    {isAuthenticated && user ? (
                      <>
                        <div className="px-3 pb-3">
                          <p className="font-medium text-ink">{user.full_name}</p>
                          <p className="text-xs text-muted">{user.email}</p>
                        </div>
                        <button type="button" onClick={handleSignOut} className="flex w-full items-center gap-3 rounded-xl px-3 py-3 font-medium text-ink hover:bg-surface">
                          <LogOut className="h-5 w-5" /> Sign out
                        </button>
                      </>
                    ) : (
                      <div className="grid grid-cols-2 gap-2">
                        <Link href="/login" className="rounded-full border border-line px-4 py-3 text-center font-medium text-ink">Sign in</Link>
                        <Link href="/signup" className="rounded-full bg-spruce px-4 py-3 text-center font-medium text-paper">Start assessment</Link>
                      </div>
                    )}
                  </div>
                </nav>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </header>

      <main className="flex-1">{children}</main>

      <footer className="border-t border-line bg-paper">
        <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 sm:py-16 lg:px-8">
          <div className="grid gap-12 lg:grid-cols-[1.2fr_0.8fr_0.8fr]">
            <div className="max-w-md">
              <Link href="/" className="inline-flex items-center gap-3">
                <Image src="/logo.svg" alt="" width={42} height={42} className="h-10 w-10 rounded-full object-cover" />
                <span className="font-display text-xl font-medium text-ink">Green Means Go</span>
              </Link>
              <p className="mt-5 text-lg leading-relaxed text-muted">
                Practical life-cycle assessment for the farms and facilities that move food.
              </p>
              <p className="mt-5 font-mono text-[0.62rem] uppercase tracking-[0.13em] text-muted">
                Available regions / Canada · Ghana · Nigeria
              </p>
            </div>
            <div>
              <p className="eyebrow">Explore</p>
              <nav className="mt-5 grid gap-3 text-sm" aria-label="Footer navigation">
                <Link href="/assessment" className="text-muted hover:text-ink">Start an assessment</Link>
                <Link href="/results" className="text-muted hover:text-ink">View results</Link>
                <Link href="/about" className="text-muted hover:text-ink">About the project</Link>
                <Link href="/contact" className="text-muted hover:text-ink">Contact</Link>
              </nav>
            </div>
            <div>
              <p className="eyebrow">Research home</p>
              <a href="https://sasellab.com/" target="_blank" rel="noopener noreferrer" className="mt-5 inline-flex items-start gap-2 text-sm leading-relaxed text-muted hover:text-ink">
                Sustainable Agrifood Systems Engineering Lab, McGill University
                <ArrowUpRight className="mt-0.5 h-4 w-4 shrink-0" />
              </a>
            </div>
          </div>
          <div className="mt-12 flex flex-col gap-3 border-t border-line pt-6 font-mono text-[0.58rem] uppercase tracking-wider text-muted sm:flex-row sm:items-center sm:justify-between">
            <span>© {new Date().getFullYear()} Green Means Go</span>
            <span>Method grounded in ISO 14040 / 14044 principles</span>
          </div>
        </div>
      </footer>
    </div>
  );
}