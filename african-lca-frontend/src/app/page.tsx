'use client';

import React from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  Sprout,
  BarChart3,
  Globe,
  Award,
  ArrowRight,
  Leaf,
  Droplets,
  Sun,
  TreePine,
  Clock,
  Factory,
  TrendingUp,
  Users,
  Building2,
  Package,
  ShoppingCart,
  Truck,
  Ship,
  Handshake,
  TrendingDown,
  CheckCircle2,
  Scale,
  FileCheck
} from 'lucide-react';
import Layout from '@/components/Layout';

export default function HomePage() {
  const features = [
    {
      icon: Sprout,
      title: 'Farm Production',
      description: 'Comprehensive farm-level assessments covering crops, livestock, and management practices',
      color: 'text-green-600 bg-green-100',
    },
    {
      icon: Factory,
      title: 'Food Processing',
      description: 'Processing facility assessments from raw materials to finished food products',
      color: 'text-blue-600 bg-blue-100',
    },
    {
      icon: Globe,
      title: 'Africa-Focused',
      description: 'Built specifically for African food systems with local data, contexts, and expertise',
      color: 'text-emerald-600 bg-emerald-100',
    },
    {
      icon: TrendingUp,
      title: 'Value Chain Insights',
      description: 'Track sustainability across the entire food value chain from farm to fork',
      color: 'text-teal-600 bg-teal-100',
    },
  ];

  const stats = [
    { label: 'Countries Supported', value: '2+', icon: Globe },
    { label: 'Impact Categories', value: '13', icon: BarChart3 },
    { label: 'Value Chain Coverage', value: 'Farm to Fork', icon: TrendingUp },
    { label: 'ISO Compliant', value: '14044', icon: Award },
  ];

  const impacts = [
    {
      icon: Leaf,
      title: 'Climate Impact',
      description: 'Track your carbon footprint and greenhouse gas emissions',
      value: 'kg CO₂-eq',
    },
    {
      icon: Droplets,
      title: 'Water Use',
      description: 'Monitor water consumption and efficiency',
      value: 'cubic meters',
    },
    {
      icon: Sun,
      title: 'Land Impact',
      description: 'Assess land use and soil health effects',
      value: 'm²-years',
    },
    {
      icon: TreePine,
      title: 'Biodiversity',
      description: 'Understand effects on local ecosystems',
      value: 'biodiversity units',
    },
  ];

  return (
    <Layout>
      {/* Hero Section */}
      <section className="relative py-16 sm:py-24 px-4 sm:px-6 lg:px-8 overflow-hidden">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center"
          >
            {/* Beta Notice */}
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="inline-flex items-center space-x-2 bg-orange-100 px-4 py-2 rounded-full border border-orange-200 mb-6"
            >
              <span className="text-sm font-semibold text-orange-600">🚀 BETA VERSION</span>
              <span className="text-sm text-orange-700">• Actively developing new features</span>
            </motion.div>

            <h1 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold text-gray-900 mb-6 leading-tight">
              Sustainable Food Systems for{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-green-600 to-emerald-600">
                Africa
              </span>
            </h1>
            <p className="text-lg sm:text-xl md:text-2xl text-gray-600 mb-10 max-w-4xl mx-auto leading-relaxed">
              Environmental impact assessments for farms and food processing companies across the African value chain
            </p>
            <div className="flex flex-col sm:flex-row justify-center gap-4">
              <Link href="/assessment">
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="bg-green-600 hover:bg-green-700 text-white px-8 py-4 rounded-xl font-semibold text-lg flex items-center space-x-3 shadow-lg transition-colors duration-200"
                >
                  <Sprout className="w-6 h-6" />
                  <span>Farm Assessment</span>
                  <ArrowRight className="w-5 h-5" />
                </motion.button>
              </Link>
              <motion.button
                whileHover={{ scale: 1.02 }}
                className="bg-gray-300 text-gray-600 px-8 py-4 rounded-xl font-semibold text-lg flex items-center space-x-3 shadow-lg cursor-not-allowed relative"
                disabled
              >
                <Factory className="w-6 h-6" />
                <span>Processing Assessment</span>
                <span className="ml-2 px-2 py-1 bg-yellow-400 text-yellow-900 text-xs font-bold rounded">COMING SOON</span>
              </motion.button>
            </div>
            
            {/* Assessment Description */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="mt-8 max-w-6xl mx-auto"
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Farm Assessment Card */}
                <div className="bg-white rounded-xl p-8 shadow-lg border-2 border-green-200">
                  <div className="flex items-center space-x-3 mb-4">
                    <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center">
                      <Sprout className="w-4 h-4 text-green-600" />
                    </div>
                    <h3 className="text-xl font-semibold text-gray-900">Farm Production</h3>
                  </div>
                  <p className="text-gray-600 mb-4">
                    Comprehensive LCA for agricultural systems following ISO 14040/14044 standards,
                    designed for African farming contexts.
                  </p>
                  <div className="space-y-2 text-sm text-gray-700">
                    <p>✓ Farm system & management analysis</p>
                    <p>✓ Cropping patterns & intercropping</p>
                    <p>✓ Soil, water & pest management</p>
                    <p>✓ Equipment & energy assessment</p>
                    <p>✓ Regional benchmarking</p>
                    <p>✓ Farmer-friendly recommendations</p>
                  </div>
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <p className="text-green-600 font-medium flex items-center text-sm">
                      <Clock className="w-4 h-4 mr-1" />
                      15-20 minutes
                    </p>
                  </div>
                </div>

                {/* Processing Assessment Card */}
                <div className="bg-white rounded-xl p-8 shadow-lg border-2 border-blue-200 relative opacity-90">
                  <div className="absolute top-4 right-4">
                    <span className="px-3 py-1 bg-yellow-400 text-yellow-900 text-xs font-bold rounded-full">
                      COMING SOON
                    </span>
                  </div>
                  <div className="flex items-center space-x-3 mb-4">
                    <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
                      <Factory className="w-4 h-4 text-blue-600" />
                    </div>
                    <h3 className="text-xl font-semibold text-gray-900">Food Processing</h3>
                  </div>
                  <p className="text-gray-600 mb-4">
                    Environmental impact assessment for food processing facilities, from raw materials
                    to finished products.
                  </p>
                  <div className="space-y-2 text-sm text-gray-700">
                    <p>✓ Raw material sourcing analysis</p>
                    <p>✓ Processing operations assessment</p>
                    <p>✓ Energy & water consumption</p>
                    <p>✓ Waste & emissions tracking</p>
                    <p>✓ Supply chain optimization</p>
                    <p>✓ Efficiency improvement strategies</p>
                  </div>
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <p className="text-gray-500 font-medium flex items-center text-sm">
                      <Clock className="w-4 h-4 mr-1" />
                      10-15 minutes
                    </p>
                  </div>
                </div>
              </div>
            </motion.div>
          </motion.div>
        </div>

        {/* Enhanced Background decoration */}
        <div className="absolute inset-0 -z-10 overflow-hidden">
          <div className="absolute top-20 left-10 w-32 h-32 bg-green-200 rounded-full opacity-20 blur-2xl animate-pulse"></div>
          <div className="absolute top-40 right-20 w-40 h-40 bg-emerald-300 rounded-full opacity-20 blur-3xl animate-pulse" style={{ animationDelay: '1s' }}></div>
          <div className="absolute bottom-20 left-1/4 w-36 h-36 bg-teal-200 rounded-full opacity-20 blur-2xl animate-pulse" style={{ animationDelay: '2s' }}></div>
          <div className="absolute bottom-40 right-1/4 w-28 h-28 bg-green-300 rounded-full opacity-15 blur-3xl animate-pulse" style={{ animationDelay: '1.5s' }}></div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-white via-green-50/30 to-emerald-50/30">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {stats.map((stat, index) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                whileHover={{ scale: 1.05, y: -5 }}
                className="text-center"
              >
                <div className="w-16 h-16 bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg">
                  <stat.icon className="w-8 h-8 text-white" />
                </div>
                <div className="text-4xl font-bold text-gray-900 mb-2">{stat.value}</div>
                <div className="text-gray-600 font-medium">{stat.label}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-white">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold text-gray-900 mb-4">
              Why Choose Green Means Go?
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed">
              Supporting sustainable food systems across Africa - from smallholder farmers to large-scale processing facilities
            </p>
          </motion.div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 sm:gap-8">
            {features.map((feature, index) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                whileHover={{ y: -8, scale: 1.02 }}
                className="bg-gradient-to-br from-white to-gray-50 rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 border border-gray-100"
              >
                <div className={`w-14 h-14 ${feature.color} rounded-xl flex items-center justify-center mb-5 shadow-md`}>
                  <feature.icon className="w-7 h-7" />
                </div>
                <h3 className="text-xl font-bold text-gray-900 mb-3">{feature.title}</h3>
                <p className="text-gray-600 leading-relaxed">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Impact Categories Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-green-50/50 via-white to-emerald-50/50">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold text-gray-900 mb-4">
              What We Measure
            </h2>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto leading-relaxed">
              Comprehensive environmental impact assessment covering all major sustainability factors
            </p>
          </motion.div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
            {impacts.map((impact, index) => (
              <motion.div
                key={impact.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                whileHover={{ scale: 1.05 }}
                className="text-center group"
              >
                <div className="w-20 h-20 bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl flex items-center justify-center mx-auto mb-5 shadow-xl group-hover:shadow-2xl transition-all duration-300 group-hover:scale-110">
                  <impact.icon className="w-10 h-10 text-white" />
                </div>
                <h3 className="text-xl font-bold text-gray-900 mb-3">{impact.title}</h3>
                <p className="text-gray-600 mb-3 leading-relaxed">{impact.description}</p>
                <span className="inline-block px-3 py-1 text-sm text-green-700 bg-green-100 rounded-full font-medium">{impact.value}</span>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Industries We Serve */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-white">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold text-gray-900 mb-4">
              Who Benefits from Green Means Go?
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed">
              Supporting sustainability across the entire African food value chain
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 gap-8 mb-12">
            {/* Farm Production */}
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
              className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-3xl p-8 border-2 border-green-200 shadow-lg hover:shadow-2xl transition-all"
            >
              <div className="w-16 h-16 bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl flex items-center justify-center mb-6 shadow-lg">
                <Sprout className="w-9 h-9 text-white" />
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-4">Farm Production</h3>
              <p className="text-gray-700 mb-6 leading-relaxed">
                From smallholder farmers to large-scale commercial operations
              </p>
              <div className="space-y-3">
                {[
                  { icon: Users, text: 'Smallholder & Family Farms' },
                  { icon: Building2, text: 'Commercial Agricultural Operations' },
                  { icon: Handshake, text: 'Agricultural Cooperatives' },
                  { icon: Sprout, text: 'Organic & Certified Farms' },
                ].map((item, idx) => (
                  <div key={idx} className="flex items-center space-x-3">
                    <div className="w-8 h-8 bg-green-500 rounded-lg flex items-center justify-center flex-shrink-0">
                      <item.icon className="w-4 h-4 text-white" />
                    </div>
                    <span className="text-gray-800 font-medium">{item.text}</span>
                  </div>
                ))}
              </div>
            </motion.div>

            {/* Food Processing */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
              className="bg-gradient-to-br from-blue-50 to-cyan-50 rounded-3xl p-8 border-2 border-blue-200 shadow-lg hover:shadow-2xl transition-all relative"
            >
              <div className="absolute top-6 right-6">
                <span className="px-3 py-1 bg-yellow-400 text-yellow-900 text-xs font-bold rounded-full">
                  COMING SOON
                </span>
              </div>
              <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-cyan-600 rounded-2xl flex items-center justify-center mb-6 shadow-lg">
                <Factory className="w-9 h-9 text-white" />
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-4">Food Processing</h3>
              <p className="text-gray-700 mb-6 leading-relaxed">
                Complete value chain from raw materials to finished products
              </p>
              <div className="space-y-3">
                {[
                  { icon: Package, text: 'Food Processing Facilities' },
                  { icon: ShoppingCart, text: 'Food Manufacturers & Brands' },
                  { icon: Truck, text: 'Food Distributors & Exporters' },
                  { icon: Building2, text: 'Agro-processing Enterprises' },
                ].map((item, idx) => (
                  <div key={idx} className="flex items-center space-x-3">
                    <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center flex-shrink-0">
                      <item.icon className="w-4 h-4 text-white" />
                    </div>
                    <span className="text-gray-800 font-medium">{item.text}</span>
                  </div>
                ))}
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Trade & Market Benefits */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-blue-600 via-indigo-600 to-purple-600 text-white overflow-hidden relative">
        {/* Background Pattern */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-0 right-0 w-96 h-96 bg-white rounded-full blur-3xl"></div>
          <div className="absolute bottom-0 left-0 w-80 h-80 bg-white rounded-full blur-3xl"></div>
        </div>

        <div className="max-w-7xl mx-auto relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <div className="inline-flex items-center justify-center w-20 h-20 bg-white/20 backdrop-blur-sm rounded-2xl mb-6">
              <Globe className="w-10 h-10 text-white" />
            </div>
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold mb-6">
              Unlock Global Trade Opportunities
            </h2>
            <p className="text-xl text-blue-100 max-w-3xl mx-auto leading-relaxed">
              Meet international sustainability requirements and access premium markets worldwide
            </p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-8">
            {/* EU Trade */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: 0.1 }}
              className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 border border-white/20 hover:bg-white/15 transition-all"
            >
              <div className="w-14 h-14 bg-blue-500 rounded-xl flex items-center justify-center mb-6">
                <Ship className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-2xl font-bold mb-4">EU Market Access</h3>
              <ul className="space-y-3 text-blue-100">
                <li className="flex items-start space-x-2">
                  <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0" />
                  <span>Meet EU Carbon Border Adjustment Mechanism (CBAM) requirements</span>
                </li>
                <li className="flex items-start space-x-2">
                  <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0" />
                  <span>Comply with EU Deforestation Regulation (EUDR)</span>
                </li>
                <li className="flex items-start space-x-2">
                  <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0" />
                  <span>Environmental Product Declarations (EPD) for exports</span>
                </li>
                <li className="flex items-start space-x-2">
                  <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0" />
                  <span>Access to premium sustainability-conscious markets</span>
                </li>
              </ul>
            </motion.div>

            {/* Global Markets */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 border border-white/20 hover:bg-white/15 transition-all"
            >
              <div className="w-14 h-14 bg-purple-500 rounded-xl flex items-center justify-center mb-6">
                <Globe className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-2xl font-bold mb-4">International Trade</h3>
              <ul className="space-y-3 text-blue-100">
                <li className="flex items-start space-x-2">
                  <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0" />
                  <span>ISO 14044 compliance for global credibility</span>
                </li>
                <li className="flex items-start space-x-2">
                  <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0" />
                  <span>Meet sustainability requirements for US, UK, Asian markets</span>
                </li>
                <li className="flex items-start space-x-2">
                  <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0" />
                  <span>Corporate ESG reporting compliance</span>
                </li>
                <li className="flex items-start space-x-2">
                  <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0" />
                  <span>Certification for organic & fair trade labels</span>
                </li>
              </ul>
            </motion.div>

            {/* African Trade */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: 0.3 }}
              className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 border border-white/20 hover:bg-white/15 transition-all"
            >
              <div className="w-14 h-14 bg-green-500 rounded-xl flex items-center justify-center mb-6">
                <Handshake className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-2xl font-bold mb-4">Intra-African Trade</h3>
              <ul className="space-y-3 text-blue-100">
                <li className="flex items-start space-x-2">
                  <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0" />
                  <span>AfCFTA sustainability standards alignment</span>
                </li>
                <li className="flex items-start space-x-2">
                  <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0" />
                  <span>Regional trade facilitation & market access</span>
                </li>
                <li className="flex items-start space-x-2">
                  <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0" />
                  <span>Pan-African Green Climate initiatives</span>
                </li>
                <li className="flex items-start space-x-2">
                  <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0" />
                  <span>Competitive advantage in regional markets</span>
                </li>
              </ul>
            </motion.div>
          </div>

          {/* Key Benefits Summary */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="mt-16 grid md:grid-cols-4 gap-6"
          >
            {[
              { icon: TrendingUp, label: 'Premium Pricing', desc: 'Command higher prices with verified sustainability credentials' },
              { icon: Scale, label: 'Regulatory Compliance', desc: 'Meet evolving international environmental regulations' },
              { icon: FileCheck, label: 'Export Certifications', desc: 'Streamline certification processes for global markets' },
              { icon: TrendingDown, label: 'Carbon Reduction', desc: 'Identify and reduce emissions to meet net-zero targets' },
            ].map((benefit, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, scale: 0.9 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: 0.5 + (idx * 0.1) }}
                whileHover={{ y: -5 }}
                className="bg-white/10 backdrop-blur-sm rounded-2xl p-6 border border-white/20 text-center"
              >
                <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center mx-auto mb-4">
                  <benefit.icon className="w-6 h-6 text-white" />
                </div>
                <h4 className="font-bold text-white text-lg mb-2">{benefit.label}</h4>
                <p className="text-blue-100 text-sm leading-relaxed">{benefit.desc}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* SASEL Lab Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 bg-white border-y border-gray-200">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="text-center"
          >
            <div className="inline-flex items-center justify-center w-16 h-16 bg-green-100 rounded-2xl mb-6">
              <Award className="w-8 h-8 text-green-600" />
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold text-gray-900 mb-4">
              Developed at McGill University
            </h2>
            <p className="text-lg text-gray-600 mb-6 max-w-3xl mx-auto leading-relaxed">
              Built by the{' '}
              <a 
                href="https://sasellab.com/" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-green-600 hover:text-green-700 font-semibold underline decoration-2 underline-offset-2"
              >
                Sustainable Agrifood Systems Engineering Lab
              </a>
              {' '}at McGill University, combining rigorous research with practical tools for African agriculture.
            </p>
          </motion.div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="relative py-24 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-green-600 via-emerald-600 to-teal-600 overflow-hidden">
        {/* Background Pattern */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-0 left-0 w-64 h-64 bg-white rounded-full blur-3xl"></div>
          <div className="absolute bottom-0 right-0 w-80 h-80 bg-white rounded-full blur-3xl"></div>
        </div>
        
        <div className="max-w-4xl mx-auto text-center relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
          >
            <h2 className="text-3xl md:text-5xl font-bold text-white mb-6 leading-tight">
              Ready to Measure Your Environmental Impact?
            </h2>
            <p className="text-xl md:text-2xl text-green-100 mb-10 leading-relaxed">
              Start with farm assessments today - processing facility tools launching soon!
            </p>
            <div className="flex flex-col sm:flex-row justify-center gap-4">
              <Link href="/assessment">
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="bg-white text-green-600 hover:bg-green-50 px-10 py-5 rounded-2xl font-bold text-lg flex items-center justify-center space-x-3 shadow-2xl transition-all duration-200"
                >
                  <Sprout className="w-6 h-6" />
                  <span>Start Farm Assessment</span>
                  <ArrowRight className="w-5 h-5" />
                </motion.button>
              </Link>
              <Link href="/about">
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="bg-green-700/30 backdrop-blur-sm text-white hover:bg-green-700/40 px-10 py-5 rounded-2xl font-bold text-lg flex items-center justify-center space-x-3 border-2 border-white/30 transition-all duration-200"
                >
                  <span>Learn More</span>
                  <ArrowRight className="w-5 h-5" />
                </motion.button>
              </Link>
            </div>
          </motion.div>
        </div>
      </section>
    </Layout>
  );
}
