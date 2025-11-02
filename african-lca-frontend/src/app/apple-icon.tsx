import { ImageResponse } from 'next/og';

// Image metadata
export const size = {
  width: 180,
  height: 180,
};
export const contentType = 'image/png';

// Image generation
export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: '20%',
        }}
      >
        <svg
          width="180"
          height="180"
          viewBox="0 0 100 100"
          style={{
            width: '70%',
            height: '70%',
          }}
        >
          {/* Africa continent outline */}
          <path
            d="M 50 15 C 48 15, 46 16, 45 18 L 42 23 C 41 25, 40 27, 40 30 L 38 37 C 37 40, 38 43, 40 45 L 42 49 C 43 51, 42 53, 40 54 L 38 57 C 36 59, 36 62, 38 64 L 42 70 C 44 72, 47 73, 50 73 L 55 72 C 58 71, 60 69, 62 67 L 65 63 C 67 60, 68 57, 68 54 L 68 47 C 68 44, 67 41, 65 39 L 62 35 C 60 33, 60 30, 62 28 L 64 23 C 65 20, 63 17, 60 16 L 55 15 C 53 15, 51 15, 50 15 Z"
            fill="rgba(255, 255, 255, 0.3)"
          />

          {/* Wheat stalk */}
          <g transform="translate(28, 30)">
            <path d="M 2 25 Q 3 12, 4 0" stroke="#fbbf24" strokeWidth="2" fill="none" strokeLinecap="round" />
            <ellipse cx="0" cy="3" rx="3" ry="4" fill="#fcd34d" />
            <ellipse cx="7" cy="7" rx="3" ry="4" fill="#fcd34d" />
            <ellipse cx="1" cy="11" rx="3" ry="4" fill="#fcd34d" />
            <ellipse cx="8" cy="15" rx="3" ry="4" fill="#fcd34d" />
            <ellipse cx="2" cy="19" rx="3" ry="4" fill="#fcd34d" />
          </g>

          {/* Growing sprout */}
          <g transform="translate(68, 40)">
            <path d="M 0 20 Q 0 10, 0 0" stroke="#ffffff" strokeWidth="3" fill="none" strokeLinecap="round" />
            <path d="M 0 8 Q -10 5, -12 0 Q -10 3, 0 8" fill="#34d399" />
            <path d="M 0 13 Q 10 10, 12 5 Q 10 8, 0 13" fill="#34d399" />
          </g>

          {/* Circular arrow */}
          <g transform="translate(50, 50)">
            <path d="M -10 -20 A 20 20 0 1 1 10 -20" stroke="#ffffff" strokeWidth="3.5" fill="none" strokeLinecap="round" opacity="0.5" />
            <path d="M 10 -20 L 15 -17 L 8 -14" stroke="#ffffff" strokeWidth="3.5" fill="none" strokeLinecap="round" strokeLinejoin="round" opacity="0.5" />
          </g>
        </svg>
      </div>
    ),
    {
      ...size,
    }
  );
}
