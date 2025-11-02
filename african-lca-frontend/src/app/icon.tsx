import { ImageResponse } from 'next/og';

// Image metadata
export const size = {
  width: 32,
  height: 32,
};
export const contentType = 'image/png';

// Image generation
export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          fontSize: 24,
          background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white',
          borderRadius: '50%',
        }}
      >
        <svg
          width="32"
          height="32"
          viewBox="0 0 100 100"
          style={{
            width: '100%',
            height: '100%',
          }}
        >
          {/* Simplified leaf symbol */}
          <path
            d="M 50 25 Q 35 30, 30 45 Q 35 40, 50 50 Q 65 40, 70 45 Q 65 30, 50 25 Z"
            fill="#ffffff"
          />
          {/* Circular arrow */}
          <path
            d="M 30 60 A 20 20 0 1 1 70 60"
            stroke="#ffffff"
            strokeWidth="5"
            fill="none"
            strokeLinecap="round"
          />
          <path
            d="M 70 60 L 75 55 L 68 52"
            stroke="#ffffff"
            strokeWidth="5"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    ),
    {
      ...size,
    }
  );
}
