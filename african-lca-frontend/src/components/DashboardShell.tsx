'use client';

// Shared shell for the signed-in dashboard: a role-aware sidebar + a top bar with the
// user menu. Pages wrap their content in <RequireAuth><DashboardShell active="…">….
// The sidebar items shown depend on the user's role (farms for farmers/officers,
// facilities for processors); everyone gets Overview and Assessments.

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter, usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  FileBarChart,
  Sprout,
  Factory,
  Menu,
  LogOut,
  ChevronDown,
  User as UserIcon,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { UserRole } from '@/lib/auth-storage';
import NewAssessmentButton from '@/components/NewAssessmentButton';
import {
  Sheet,
  SheetContent,
  SheetTrigger,
  SheetTitle,
} from '@/components/ui/sheet';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

export type DashboardSection = 'overview' | 'assessments' | 'farms' | 'facilities';

const ROLE_LABEL: Record<string, string> = {
  farmer: 'Farmer',
  extension_officer: 'Extension officer',
  processor: 'Processor',
  researcher: 'Researcher',
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
    { key: 'overview', label: 'Overview', href: '/dashboard', icon: LayoutDashboard, roles: ['farmer', 'extension_officer', 'processor', 'researcher'] },
    { key: 'assessments', label: 'Assessments', href: '/dashboard/assessments', icon: FileBarChart, roles: ['farmer', 'extension_officer', 'processor', 'researcher'] },
    // Only owners keep a registry. Officers/researchers assess via the wizard instead.
    { key: 'farms', label: 'My farms', href: '/dashboard/farms', icon: Sprout, roles: ['farmer'] },
    { key: 'facilities', label: 'My facilities', href: '/dashboard/facilities', icon: Factory, roles: ['processor'] },
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
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const nav = navForRole(user?.role);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname]);

  const handleSignOut = async () => {
    await logout();
    router.push('/');
  };

  const SidebarContent = (
    <div className="flex h-full flex-col">
      <Link href="/" className="flex items-center gap-2 px-5 h-16 border-b border-line focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-moss/80">
                <Image src="/logo.svg" alt="Green Means Go" width={32} height={32} aria-hidden="true" />
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
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-moss/80 ${
                isActive ? 'bg-moss/10 text-spruce' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              }`}
            >
              <Icon className="w-5 h-5" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-gray-100">
        <NewAssessmentButton block onNavigate={() => setMobileMenuOpen(false)} />
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex fixed inset-y-0 left-0 w-64 flex-col bg-white border-r border-gray-200 shadow-sm z-10">
        {SidebarContent}
      </aside>

      <div className="flex-1 lg:pl-64 flex flex-col min-h-screen">
        {/* Top bar */}
        <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center justify-between gap-3 border-b border-gray-200 bg-white/80 backdrop-blur px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
              <SheetTrigger asChild>
                <button
                  type="button"
                  aria-label="Open navigation menu"
                  className="lg:hidden p-2 -ml-2 rounded-lg text-gray-500 hover:bg-gray-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-moss/80"
                >
                  <Menu className="w-5 h-5" />
                </button>
              </SheetTrigger>
              <SheetContent side="left" className="p-0 w-[280px] border-r-gray-200" showCloseButton={false}>
                <SheetTitle className="sr-only">Navigation Menu</SheetTitle>
                {SidebarContent}
              </SheetContent>
            </Sheet>
            <h1 className="text-lg font-semibold text-gray-900">{title}</h1>
          </div>

          {user && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  className="flex items-center gap-2 rounded-full py-1 pl-1 pr-2 hover:bg-gray-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-moss/80 transition-colors"
                >
                  <span className="grid place-items-center w-8 h-8 rounded-full bg-spruce text-white text-sm font-semibold">
                    {initials(user.full_name)}
                  </span>
                  <span className="hidden sm:block text-left mr-1">
                    <span className="block text-sm font-medium text-gray-900 leading-tight">{user.full_name}</span>
                    <span className="block text-[0.7rem] text-gray-500 leading-tight">{ROLE_LABEL[user.role]}</span>
                  </span>
                  <ChevronDown className="w-4 h-4 text-gray-400" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56 mt-1 p-2 border border-gray-100 shadow-xl rounded-xl">
                <div className="px-2 py-1.5 mb-1">
                  <p className="font-medium text-gray-900 truncate text-sm">{user.full_name}</p>
                  <p className="text-xs text-gray-500 truncate">{user.email}</p>
                </div>
                <DropdownMenuSeparator className="bg-gray-100" />
                <Link href="/">
                  <DropdownMenuItem className="cursor-pointer my-1 rounded-md">
                    <LayoutDashboard className="mr-2 w-4 h-4 text-gray-500" />
                    <span className="text-gray-700">Back to site</span>
                  </DropdownMenuItem>
                </Link>
                <DropdownMenuItem onClick={handleSignOut} className="cursor-pointer text-red-600 focus:text-red-600 focus:bg-red-50 rounded-md">
                  <LogOut className="mr-2 w-4 h-4" />
                  <span>Sign out</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}

export { ROLE_LABEL };
