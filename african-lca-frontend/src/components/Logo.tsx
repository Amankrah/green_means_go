'use client';

import React from 'react';

interface LogoProps {
  className?: string;
  size?: number;
}

export default function Logo({ className = '', size = 40 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Background circle with gradient */}
      <defs>
        <linearGradient id="logoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#10b981" />
          <stop offset="100%" stopColor="#059669" />
        </linearGradient>
        <linearGradient id="leafGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#34d399" />
          <stop offset="100%" stopColor="#10b981" />
        </linearGradient>
      </defs>

      {/* Circular background */}
      <circle cx="50" cy="50" r="48" fill="url(#logoGradient)" />

      {/* Stylized Africa continent shape */}
      <path
        d="M 50 20
           C 48 20, 46 21, 45 23
           L 42 28
           C 41 30, 40 32, 40 35
           L 38 42
           C 37 45, 38 48, 40 50
           L 42 54
           C 43 56, 42 58, 40 59
           L 38 62
           C 36 64, 36 67, 38 69
           L 42 75
           C 44 77, 47 78, 50 78
           L 55 77
           C 58 76, 60 74, 62 72
           L 65 68
           C 67 65, 68 62, 68 59
           L 68 52
           C 68 49, 67 46, 65 44
           L 62 40
           C 60 38, 60 35, 62 33
           L 64 28
           C 65 25, 63 22, 60 21
           L 55 20
           C 53 20, 51 20, 50 20 Z"
        fill="rgba(255, 255, 255, 0.25)"
      />

      {/* Wheat/Grain stalk - representing agriculture */}
      <g transform="translate(30, 35)">
        {/* Stalk */}
        <path
          d="M 2 30 Q 3 15, 4 0"
          stroke="#fbbf24"
          strokeWidth="1.5"
          fill="none"
          strokeLinecap="round"
        />
        {/* Grain seeds */}
        <ellipse cx="0" cy="4" rx="2.5" ry="3.5" fill="#fcd34d" />
        <ellipse cx="6" cy="8" rx="2.5" ry="3.5" fill="#fcd34d" />
        <ellipse cx="1" cy="12" rx="2.5" ry="3.5" fill="#fcd34d" />
        <ellipse cx="7" cy="16" rx="2.5" ry="3.5" fill="#fcd34d" />
        <ellipse cx="2" cy="20" rx="2.5" ry="3.5" fill="#fcd34d" />
      </g>

      {/* Growing sprout - representing sustainability */}
      <g transform="translate(65, 45)">
        {/* Stem */}
        <path
          d="M 0 20 Q 0 10, 0 0"
          stroke="#ffffff"
          strokeWidth="2"
          fill="none"
          strokeLinecap="round"
        />
        {/* Left leaf */}
        <path
          d="M 0 8 Q -8 5, -10 0 Q -8 3, 0 8"
          fill="url(#leafGradient)"
        />
        {/* Right leaf */}
        <path
          d="M 0 12 Q 8 9, 10 4 Q 8 7, 0 12"
          fill="url(#leafGradient)"
        />
      </g>

      {/* Circular arrow - representing lifecycle/sustainability cycle */}
      <g transform="translate(50, 50)">
        <path
          d="M -8 -18 A 18 18 0 1 1 8 -18"
          stroke="#ffffff"
          strokeWidth="2.5"
          fill="none"
          strokeLinecap="round"
          opacity="0.4"
        />
        {/* Arrow head */}
        <path
          d="M 8 -18 L 12 -15 L 6 -12"
          stroke="#ffffff"
          strokeWidth="2.5"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity="0.4"
        />
      </g>
    </svg>
  );
}

export function LogoIcon({ className = '', size = 24 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Simplified version for favicon */}
      <defs>
        <linearGradient id="iconGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#10b981" />
          <stop offset="100%" stopColor="#059669" />
        </linearGradient>
      </defs>

      <circle cx="50" cy="50" r="48" fill="url(#iconGradient)" />

      {/* Simplified leaf symbol */}
      <path
        d="M 50 25 Q 35 30, 30 45 Q 35 40, 50 50 Q 65 40, 70 45 Q 65 30, 50 25 Z"
        fill="#ffffff"
      />

      {/* Circular arrow */}
      <path
        d="M 30 60 A 20 20 0 1 1 70 60"
        stroke="#ffffff"
        strokeWidth="4"
        fill="none"
        strokeLinecap="round"
      />
      <path
        d="M 70 60 L 75 55 L 68 52"
        stroke="#ffffff"
        strokeWidth="4"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
