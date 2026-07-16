'use client';

// Shared shell for the signed-in dashboard: a role-aware sidebar + a top bar with the
// user menu. Pages wrap their content in <RequireAuth><DashboardShell active="…">….
// The sidebar items shown depend on the user's role (farms for farmers/officers,
// facilities for processors); everyone gets Overview and Assessments.

import React, { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import {
  LayoutDashboard,
  FileBarChart,
  Sprout,
  Factory,
  Menu,
  LogOut,
  ChevronDown,
  Plus,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { UserRole } from '@/lib/auth-storage';

export type DashboardSection = 'overview' | 'assessments' | 'farms' | 'facilities';

const ROLE_LABEL: Record<string, string> = {
  farmer: 'Farmer',
  extension_officer: 'Extension officer',
  processor: 'Processor',
};

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] || '') + (parts[1]?.[0] || '')).toUpperCase() || 'U';
}

interface NavItem {
  key: DashboardSection;
  label: string;
  href: string;
  icon: React.ElementType;
  roles: UserRole[];
}

function navForRole(role: UserRole | undefined): NavItem[] {
  const items: NavItem[] = [
    { key: 'overview', label: 'Overview', href: '/dashboard', icon: LayoutDashboard, roles: ['farmer', 'extension_officer', 'processor'] },
    { key: 'assessments', label: 'Assessments', href: '/dashboard/assessments', icon: FileBarChart, roles: ['farmer', 'extension_officer', 'processor'] },
    { key: 'farms', label: role === 'extension_officer' ? 'Clients & farms' : 'My farms', href: '/dashboard/farms', icon: Sprout, roles: ['farmer', 'extension_officer'] },
    { key: 'facilities', label: 'Facilities', href: '/dashboard/facilities', icon: Factory, roles: ['processor'] },
  ];
  return items.filter((i) => (role ? i.roles.includes(role) : false));
}

export default function DashboardShell({
  active,
  title,
  children,
}: {
  active: DashboardSection;
  title: string;
  children: React.ReactNode;
}) {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const nav = navForRole(user?.role);
  const isProcessor = user?.role === 'processor';
  const newAssessmentHref = isProcessor ? '/processing-assessment' : '/assessment';

  const handleSignOut = async () => {
    setUserMenuOpen(false);
    await logout();
    router.push('/');
  };

  const SidebarContent = (
    <div className="flex h-full flex-col">
      <Link href="/" className="flex items-center gap-2 px-5 h-16 border-b border-line">
        <Image src="/logo.svg" alt="Green Means Go" width={32} height={32} />
        <span className="font-display text-lg font-medium text-ink">Green Means Go</span>
      </Link>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {nav.map((item) => {
          const Icon = item.icon;
          const isActive = item.key === active;
          return (
            <Link
              key={item.key}
              href={item.href}
              onClick={() => setSidebarOpen(false)}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive ? 'bg-moss/10 text-spruce' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              }`}
            >
              <Icon className="w-5 h-5" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="p-3">
        <Link
          href={newAssessmentHref}
          onClick={() => setSidebarOpen(false)}
          className="flex items-center justify-center gap-2 rounded-lg bg-spruce px-3 py-2.5 text-sm font-medium text-white hover:bg-ink transition-colors"
        >
          <Plus className="w-4 h-4" /> New assessment
        </Link>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex fixed inset-y-0 left-0 w-64 flex-col bg-white border-r border-gray-200">
        {SidebarContent}
      </aside>

      {/* Mobile sidebar */}
      {sidebarOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div className="fixed inset-0 bg-black/30" onClick={() => setSidebarOpen(false)} />
          <aside className="relative w-64 bg-white border-r border-gray-200">{SidebarContent}</aside>
        </div>
      )}

      <div className="lg:pl-64">
        {/* Top bar */}
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-gray-200 bg-white/80 backdrop-blur px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              aria-label="Open menu"
              className="lg:hidden p-2 rounded-lg text-gray-500 hover:bg-gray-100"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="w-5 h-5" />
            </button>
            <h1 className="text-lg font-semibold text-gray-900">{title}</h1>
          </div>

          {user && (
            <div className="relative">
              <button
                type="button"
                onClick={() => setUserMenuOpen((v) => !v)}
                className="flex items-center gap-2 rounded-lg py-1 pl-1 pr-2 hover:bg-gray-100 transition-colors"
              >
                <span className="grid place-items-center w-9 h-9 rounded-full bg-spruce text-white text-sm font-semibold">
                  {initials(user.full_name)}
                </span>
                <span className="hidden sm:block text-left">
                  <span className="block text-sm font-medium text-gray-900 leading-tight">{user.full_name}</span>
                  <span className="block text-xs text-gray-500 leading-tight">{ROLE_LABEL[user.role]}</span>
                </span>
                <ChevronDown className="w-4 h-4 text-gray-400" />
              </button>
              {userMenuOpen && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setUserMenuOpen(false)} />
                  <div className="absolute right-0 mt-2 w-56 z-50 rounded-xl bg-white shadow-xl border border-gray-100 py-2">
                    <div className="px-4 py-2 border-b border-gray-100">
                      <p className="font-medium text-gray-900 truncate">{user.full_name}</p>
                      <p className="text-xs text-gray-500 truncate">{user.email}</p>
                    </div>
                    <Link href="/" className="flex items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">
                      Back to site
                    </Link>
                    <button
                      type="button"
                      onClick={handleSignOut}
                      className="w-full flex items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                    >
                      <LogOut className="w-4 h-4" /> Sign out
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </header>

        <main className="p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}

export { ROLE_LABEL };
