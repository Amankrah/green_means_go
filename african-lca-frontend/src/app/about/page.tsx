'use client';

import React from 'react';
import { motion } from 'framer-motion';
import Link from 'next/link';

// Force dynamic rendering for this page
export const dynamic = 'force-dynamic';
import {
  Sprout,
  Globe,
  Award,
  Users,
  Target,
  Heart,
  ExternalLink,
  BookOpen,
  Lightbulb,
  TrendingUp,
  Building2,
  Factory,
  Package,
  Ship,
  Handshake,
  ShoppingCart,
  Truck,
  CheckCircle2,
  Scale,
  FileCheck,
  TrendingDown
} from 'lucide-react';
import Layout from '@/components/Layout';

export default function AboutPage() {
  const values = [
    {
      icon: Target,
      title: 'Accuracy',
      description: 'ISO 14044 compliant methodology with rigorous data quality standards',
    },
    {
      icon: Globe,
      title: 'African Context',
      description: 'Built specifically for African food systems with local data and expertise',
    },
    {
      icon: Users,
      title: 'Accessibility',
      description: 'User-friendly tools that make professional LCA accessible to all farmers',
    },
    {
      icon: Heart,
      title: 'Sustainability',
      description: 'Driving sustainable practices across African agriculture and food processing',
    },
  ];

  const features = [
    {
      icon: Sprout,
      title: 'Farm-Level Assessment',
      description: 'Comprehensive environmental impact analysis for agricultural operations including crop production, livestock, and management practices.',
    },
    {
      icon: BookOpen,
      title: 'ISO 14044 Compliance',
      description: 'Professional LCA methodology following international standards for credible and comparable results.',
    },
    {
      icon: TrendingUp,
      title: 'Actionable Insights',
      description: 'Clear recommendations and benchmarking to help farmers improve sustainability performance.',
    },
    {
      icon: Lightbulb,
      title: 'Research-Backed',
      description: 'Developed through rigorous academic research and validated with real-world African agricultural data.',
    },
  ];

  return (
    <Layout>
      <div className="min-h-screen">
        {/* Hero Section */}
        <section className="relative bg-gradient-to-br from-green-600 via-emerald-600 to-teal-600 text-white py-20 pb-32">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="text-center"
            >
              <h1 className="text-4xl sm:text-5xl font-bold mb-6">
                About Green Means Go
              </h1>
              <p className="text-xl sm:text-2xl text-green-50 max-w-3xl mx-auto mb-8">
                Empowering African food systems with professional sustainability assessment tools
              </p>
            </motion.div>
          </div>
          
          {/* Decorative wave */}
          <div className="absolute bottom-0 left-0 right-0">
            <svg viewBox="0 0 1440 120" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full">
              <path d="M0 0L60 10C120 20 240 40 360 46.7C480 53 600 47 720 43.3C840 40 960 40 1080 46.7C1200 53 1320 67 1380 73.3L1440 80V120H1380C1320 120 1200 120 1080 120C960 120 840 120 720 120C600 120 480 120 360 120C240 120 120 120 60 120H0V0Z" fill="rgb(236 253 245)"/>
            </svg>
          </div>
        </section>

        {/* Mission Section */}
        <section className="py-16 bg-green-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
              className="max-w-4xl mx-auto"
            >
              <div className="bg-white rounded-2xl shadow-xl p-8 sm:p-12">
                <h2 className="text-3xl font-bold text-gray-900 mb-6 text-center">
                  Our Mission
                </h2>
                <p className="text-lg text-gray-700 leading-relaxed mb-6">
                  Green Means Go is a professional Life Cycle Assessment (LCA) platform designed specifically 
                  for African food systems. We provide farmers, processors, and food businesses with the tools 
                  to measure, understand, and improve their environmental sustainability.
                </p>
                <p className="text-lg text-gray-700 leading-relaxed">
                  Built on rigorous scientific methodology and validated with real African agricultural data, 
                  our platform makes professional sustainability assessment accessible and actionable for all 
                  stakeholders in the food value chain.
                </p>
              </div>
            </motion.div>
          </div>
        </section>

        {/* Core Values */}
        <section className="py-16 bg-white">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
              className="text-center mb-12"
            >
              <h2 className="text-3xl font-bold text-gray-900 mb-4">
                Our Core Values
              </h2>
              <p className="text-lg text-gray-600 max-w-2xl mx-auto">
                Principles that guide our work and commitment to African agriculture
              </p>
            </motion.div>

            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
              {values.map((value, index) => (
                <motion.div
                  key={value.title}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.6, delay: index * 0.1 }}
                  className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-xl p-6 border border-green-100 hover:shadow-lg transition-shadow duration-300"
                >
                  <div className="bg-green-600 rounded-lg w-12 h-12 flex items-center justify-center mb-4">
                    <value.icon className="w-6 h-6 text-white" />
                  </div>
                  <h3 className="text-xl font-semibold text-gray-900 mb-2">
                    {value.title}
                  </h3>
                  <p className="text-gray-600">
                    {value.description}
                  </p>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section className="py-16 bg-gradient-to-br from-green-50 via-emerald-50 to-teal-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
              className="text-center mb-12"
            >
              <h2 className="text-3xl font-bold text-gray-900 mb-4">
                What We Offer
              </h2>
              <p className="text-lg text-gray-600 max-w-2xl mx-auto">
                Professional LCA tools built for African food systems
              </p>
            </motion.div>

            <div className="grid md:grid-cols-2 gap-8">
              {features.map((feature, index) => (
                <motion.div
                  key={feature.title}
                  initial={{ opacity: 0, x: index % 2 === 0 ? -20 : 20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.6, delay: index * 0.1 }}
                  className="bg-white rounded-xl p-8 shadow-lg hover:shadow-xl transition-shadow duration-300"
                >
                  <div className="flex items-start space-x-4">
                    <div className="bg-green-100 rounded-lg p-3 flex-shrink-0">
                      <feature.icon className="w-8 h-8 text-green-600" />
                    </div>
                    <div>
                      <h3 className="text-xl font-semibold text-gray-900 mb-2">
                        {feature.title}
                      </h3>
                      <p className="text-gray-600 leading-relaxed">
                        {feature.description}
                      </p>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        {/* Industries Served */}
        <section className="py-20 bg-gradient-to-br from-green-50 to-emerald-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.8 }}
              className="text-center mb-16"
            >
              <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
                Industries We Serve
              </h2>
              <p className="text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed">
                Comprehensive sustainability solutions for every stage of the African food value chain
              </p>
            </motion.div>

            <div className="grid lg:grid-cols-2 gap-10 mb-16">
              {/* Farm Production Industries */}
              <motion.div
                initial={{ opacity: 0, x: -30 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6 }}
                className="bg-white rounded-3xl p-10 shadow-xl border-2 border-green-200"
              >
                <div className="flex items-center space-x-4 mb-6">
                  <div className="w-16 h-16 bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl flex items-center justify-center shadow-lg">
                    <Sprout className="w-9 h-9 text-white" />
                  </div>
                  <div>
                    <h3 className="text-2xl font-bold text-gray-900">Farm Production</h3>
                    <p className="text-green-600 font-medium">Available Now</p>
                  </div>
                </div>
                <p className="text-gray-700 mb-6 leading-relaxed">
                  Empowering farmers and agricultural businesses with data-driven sustainability insights
                </p>
                <div className="space-y-4">
                  {[
                    { icon: Users, title: 'Smallholder & Family Farms', desc: 'Optimize practices and access premium markets' },
                    { icon: Building2, title: 'Commercial Farms', desc: 'Meet corporate sustainability targets and ESG goals' },
                    { icon: Handshake, title: 'Agricultural Cooperatives', desc: 'Collective sustainability reporting and certification' },
                    { icon: Sprout, title: 'Organic & Certified Producers', desc: 'Verify and enhance environmental credentials' },
                  ].map((item, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, x: -10 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      viewport={{ once: true }}
                      transition={{ delay: 0.7 + (idx * 0.1) }}
                      className="flex items-start space-x-3 bg-green-50 rounded-xl p-4 border border-green-100"
                    >
                      <div className="w-10 h-10 bg-green-500 rounded-lg flex items-center justify-center flex-shrink-0">
                        <item.icon className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <h4 className="font-bold text-gray-900 mb-1">{item.title}</h4>
                        <p className="text-sm text-gray-600 leading-relaxed">{item.desc}</p>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </motion.div>

              {/* Food Processing Industries */}
              <motion.div
                initial={{ opacity: 0, x: 30 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6 }}
                className="bg-white rounded-3xl p-10 shadow-xl border-2 border-blue-200 relative"
              >
                <div className="absolute top-6 right-6">
                  <span className="px-3 py-1 bg-yellow-400 text-yellow-900 text-xs font-bold rounded-full shadow-md">
                    COMING SOON
                  </span>
                </div>
                <div className="flex items-center space-x-4 mb-6">
                  <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-cyan-600 rounded-2xl flex items-center justify-center shadow-lg">
                    <Factory className="w-9 h-9 text-white" />
                  </div>
                  <div>
                    <h3 className="text-2xl font-bold text-gray-900">Food Processing</h3>
                    <p className="text-blue-600 font-medium">Launching Soon</p>
                  </div>
                </div>
                <p className="text-gray-700 mb-6 leading-relaxed">
                  Complete environmental assessments from raw materials to finished products
                </p>
                <div className="space-y-4">
                  {[
                    { icon: Package, title: 'Processing Facilities', desc: 'Measure and optimize production environmental impacts' },
                    { icon: ShoppingCart, title: 'Food Manufacturers', desc: 'Meet buyer sustainability requirements' },
                    { icon: Truck, title: 'Distributors & Exporters', desc: 'Supply chain carbon footprint tracking' },
                    { icon: Building2, title: 'Agro-processing SMEs', desc: 'Scale sustainably with verified data' },
                  ].map((item, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, x: 10 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      viewport={{ once: true }}
                      transition={{ delay: 0.7 + (idx * 0.1) }}
                      className="flex items-start space-x-3 bg-blue-50 rounded-xl p-4 border border-blue-100 opacity-75"
                    >
                      <div className="w-10 h-10 bg-blue-500 rounded-lg flex items-center justify-center flex-shrink-0">
                        <item.icon className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <h4 className="font-bold text-gray-900 mb-1">{item.title}</h4>
                        <p className="text-sm text-gray-600 leading-relaxed">{item.desc}</p>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </motion.div>
            </div>
          </div>
        </section>

        {/* Trade Benefits Section */}
        <section className="py-20 bg-gradient-to-br from-indigo-600 via-purple-600 to-blue-600 text-white">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.8 }}
              className="text-center mb-16"
            >
              <div className="inline-flex items-center justify-center w-20 h-20 bg-white/20 backdrop-blur-sm rounded-2xl mb-6">
                <Ship className="w-10 h-10 text-white" />
              </div>
              <h2 className="text-3xl sm:text-4xl font-bold mb-6">
                Opening Doors to Global Markets
              </h2>
              <p className="text-xl text-indigo-100 max-w-4xl mx-auto leading-relaxed">
                Verified sustainability data is your passport to premium international and regional markets. 
                Meet trade requirements, unlock new opportunities, and command better prices.
              </p>
            </motion.div>

            <div className="grid md:grid-cols-3 gap-8 mb-12">
              {/* EU Markets */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: 0.1 }}
                whileHover={{ y: -5 }}
                className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 border border-white/20"
              >
                <div className="w-14 h-14 bg-blue-500 rounded-xl flex items-center justify-center mb-6 shadow-lg">
                  <Ship className="w-8 h-8 text-white" />
                </div>
                <h3 className="text-2xl font-bold mb-4">🇪🇺 European Union</h3>
                <ul className="space-y-3 text-indigo-100 text-sm">
                  <li className="flex items-start space-x-2">
                    <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0 text-green-300" />
                    <span><strong>CBAM Compliance:</strong> Meet Carbon Border Adjustment Mechanism requirements</span>
                  </li>
                  <li className="flex items-start space-x-2">
                    <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0 text-green-300" />
                    <span><strong>EUDR Readiness:</strong> Comply with EU Deforestation Regulation</span>
                  </li>
                  <li className="flex items-start space-x-2">
                    <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0 text-green-300" />
                    <span><strong>Farm to Fork:</strong> Align with EU sustainable food systems strategy</span>
                  </li>
                  <li className="flex items-start space-x-2">
                    <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0 text-green-300" />
                    <span><strong>Premium Access:</strong> Environmental Product Declarations (EPD) for exports</span>
                  </li>
                </ul>
              </motion.div>

              {/* Global Markets */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: 0.2 }}
                whileHover={{ y: -5 }}
                className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 border border-white/20"
              >
                <div className="w-14 h-14 bg-purple-500 rounded-xl flex items-center justify-center mb-6 shadow-lg">
                  <Globe className="w-8 h-8 text-white" />
                </div>
                <h3 className="text-2xl font-bold mb-4">🌍 Global Markets</h3>
                <ul className="space-y-3 text-indigo-100 text-sm">
                  <li className="flex items-start space-x-2">
                    <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0 text-green-300" />
                    <span><strong>US & UK Markets:</strong> Meet sustainability disclosure requirements</span>
                  </li>
                  <li className="flex items-start space-x-2">
                    <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0 text-green-300" />
                    <span><strong>Asian Markets:</strong> Carbon footprint documentation for exports</span>
                  </li>
                  <li className="flex items-start space-x-2">
                    <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0 text-green-300" />
                    <span><strong>Corporate Buyers:</strong> ESG compliance for supply chain partners</span>
                  </li>
                  <li className="flex items-start space-x-2">
                    <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0 text-green-300" />
                    <span><strong>Certifications:</strong> Support for organic, fair trade, Rainforest Alliance</span>
                  </li>
                </ul>
              </motion.div>

              {/* Intra-African Trade */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: 0.3 }}
                whileHover={{ y: -5 }}
                className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 border border-white/20"
              >
                <div className="w-14 h-14 bg-green-500 rounded-xl flex items-center justify-center mb-6 shadow-lg">
                  <Handshake className="w-8 h-8 text-white" />
                </div>
                <h3 className="text-2xl font-bold mb-4">🌍 Intra-African Trade</h3>
                <ul className="space-y-3 text-indigo-100 text-sm">
                  <li className="flex items-start space-x-2">
                    <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0 text-green-300" />
                    <span><strong>AfCFTA Alignment:</strong> Meet African Continental Free Trade Area standards</span>
                  </li>
                  <li className="flex items-start space-x-2">
                    <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0 text-green-300" />
                    <span><strong>Regional Integration:</strong> Facilitate cross-border agricultural trade</span>
                  </li>
                  <li className="flex items-start space-x-2">
                    <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0 text-green-300" />
                    <span><strong>Pan-African Standards:</strong> ECOWAS and AU sustainable agriculture initiatives</span>
                  </li>
                  <li className="flex items-start space-x-2">
                    <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0 text-green-300" />
                    <span><strong>Market Leadership:</strong> Stand out in competitive regional markets</span>
                  </li>
                </ul>
              </motion.div>
            </div>

            {/* Business Benefits */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.8, delay: 0.4 }}
              className="bg-white rounded-3xl p-10 shadow-2xl"
            >
              <h3 className="text-2xl font-bold text-gray-900 mb-8 text-center">
                Tangible Business Benefits
              </h3>
              <div className="grid md:grid-cols-4 gap-6">
                {[
                  { icon: TrendingUp, title: 'Premium Pricing', desc: '10-30% price premiums for verified sustainable products' },
                  { icon: Scale, title: 'Regulatory Compliance', desc: 'Meet mandatory environmental disclosure requirements' },
                  { icon: FileCheck, title: 'Faster Certifications', desc: 'Streamlined process for organic, fair trade certifications' },
                  { icon: TrendingDown, title: 'Cost Reduction', desc: 'Identify efficiency opportunities and reduce input costs' },
                ].map((benefit, idx) => (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.6 + (idx * 0.1) }}
                    whileHover={{ scale: 1.05 }}
                    className="text-center"
                  >
                    <div className="w-14 h-14 bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg">
                      <benefit.icon className="w-7 h-7 text-white" />
                    </div>
                    <h4 className="font-bold text-gray-900 mb-2">{benefit.title}</h4>
                    <p className="text-sm text-gray-600 leading-relaxed">{benefit.desc}</p>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          </div>
        </section>

        {/* Development Section */}
        <section className="py-16 bg-white">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
              className="max-w-4xl mx-auto"
            >
              <div className="bg-gradient-to-br from-green-600 to-emerald-600 rounded-2xl shadow-2xl p-8 sm:p-12 text-white">
                <div className="flex items-center justify-center mb-6">
                  <Award className="w-12 h-12" />
                </div>
                <h2 className="text-3xl font-bold mb-6 text-center">
                  Developed at McGill University
                </h2>
                <p className="text-lg text-green-50 leading-relaxed mb-6 text-center">
                  Green Means Go is developed at the{' '}
                  <a 
                    href="https://sasellab.com/" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="font-bold underline decoration-2 hover:text-white transition-colors inline-flex items-center gap-1"
                  >
                    Sustainable Agrifood Systems Engineering Lab (SASEL)
                    <ExternalLink className="w-4 h-4" />
                  </a>
                  {' '}at McGill University, Canada.
                </p>
                <p className="text-green-50 leading-relaxed text-center">
                  Our team combines expertise in agricultural engineering, environmental science, 
                  and digital innovation to create tools that drive sustainable food systems across Africa.
                </p>
                <div className="mt-8 text-center">
                  <Link
                    href="/contact"
                    className="inline-flex items-center space-x-2 bg-white text-green-600 px-6 py-3 rounded-lg font-semibold hover:bg-green-50 transition-colors duration-200"
                  >
                    <span>Get in Touch</span>
                    <ExternalLink className="w-5 h-5" />
                  </Link>
                </div>
              </div>
            </motion.div>
          </div>
        </section>

        {/* Beta Notice */}
        <section className="py-12 bg-orange-50 border-y border-orange-200">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <div className="inline-flex items-center space-x-2 bg-orange-100 px-4 py-2 rounded-full border border-orange-300 mb-4">
              <span className="text-2xl">🚀</span>
              <span className="font-bold text-orange-600">BETA VERSION</span>
            </div>
            <h3 className="text-2xl font-bold text-gray-900 mb-4">
              We&apos;re Currently in Beta
            </h3>
            <p className="text-lg text-gray-700 max-w-2xl mx-auto">
              Green Means Go is actively being developed and improved. We welcome feedback 
              from early users to help us create the best possible tool for African food systems. 
              Your input matters!
            </p>
          </div>
        </section>
      </div>
    </Layout>
  );
}

