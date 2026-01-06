# Green Means Go - African Food Systems LCA Platform

Professional Life Cycle Assessment (LCA) platform for African food systems. Assess environmental impact of farms and food processing facilities following ISO 14044 standards.

## About

Green Means Go is developed at the [Sustainable Agrifood Systems Engineering Lab (SASEL)](https://sasellab.com/) at McGill University. The platform provides comprehensive sustainability assessments for African agricultural and food processing operations.

### Key Features

- 🌾 **Farm Production Assessment**: Comprehensive farm-level LCA covering crops, livestock, and management practices
- 🏭 **Food Processing Assessment**: Processing facility assessments from raw materials to finished products
- 🌍 **Africa-Focused**: Built specifically for African food systems with local data and contexts
- 📊 **ISO 14044 Compliant**: Professional LCA methodology following international standards
- 🎯 **Regional Coverage**: Currently supporting Ghana and Nigeria, expanding across Africa

## Technology Stack

- **Framework**: Next.js 15 (React 19)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Animation**: Framer Motion
- **Forms**: React Hook Form + Zod validation
- **API**: RESTful backend integration

## Getting Started

### Prerequisites

- Node.js 18+ or Bun
- npm, yarn, pnpm, or bun

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/green-means-go.git
cd green-means-go/african-lca-frontend

# Install dependencies
npm install
# or
bun install

# Set up environment variables
cp .env.example .env.local
```

### Development

Run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the application.

### Building for Production

```bash
npm run build
npm run start
```

## Project Structure

```
african-lca-frontend/
├── src/
│   ├── app/              # Next.js app router pages
│   ├── components/       # React components
│   ├── lib/             # Utility functions and API
│   ├── types/           # TypeScript type definitions
│   └── config/          # Configuration files
├── public/              # Static assets
└── README.md
```

## Environment Variables

Create a `.env.local` file with the following variables:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SITE_URL=http://localhost:3000
NEXT_PUBLIC_GA_TRACKING_ID=your-ga-id
NEXT_PUBLIC_GTM_ID=your-gtm-id
```

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting pull requests.

## License

All rights reserved © 2025 Green Means Go

## Contact & Support

- **Lab**: [Sustainable Agrifood Systems Engineering Lab](https://sasellab.com/)
- **Email**: ebenezer.kwofie@mcgill.ca
- **Address**: 2111 Lakeshore Road, Sainte-Anne-de-Bellevue, Quebec, Canada H9X 3V9
- **Phone**: +1-514-398-7776

## Acknowledgments

Developed at the [Sustainable Agrifood Systems Engineering Lab](https://sasellab.com/) at McGill University.

---

Built with ❤️ for sustainable African food systems
