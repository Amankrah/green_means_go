'use client';

import React from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { 
  Sprout, 
  BarChart3, 
  Globe, 
  Users, 
  Award, 
  ArrowRight,
  Leaf,
  Droplets,
  Sun,
  TreePine,
  Clock
} from 'lucide-react';
import Layout from '@/components/Layout';

export default function HomePage() {
  const features = [
    {
      icon: Sprout,
      title: 'Farm Assessment',
      description: 'Simple sustainability assessment for your crops using minimal information',
      color: 'text-green-600 bg-green-100',
    },
    {
      icon: BarChart3,
      title: 'Detailed Results',
      description: 'Get comprehensive environmental impact analysis with actionable recommendations',
      color: 'text-blue-600 bg-blue-100',
    },
    {
      icon: Globe,
      title: 'Africa-Focused',
      description: 'Built specifically for African farming systems with local data and expertise',
      color: 'text-emerald-600 bg-emerald-100',
    },
    {
      icon: Users,
      title: 'Farmer Friendly',
      description: 'No technical expertise required - designed for practical farm use',
      color: 'text-teal-600 bg-teal-100',
    },
  ];

  const stats = [
    { label: 'Countries Supported', value: '2+', icon: Globe },
    { label: 'Impact Categories', value: '13', icon: BarChart3 },
    { label: 'Farmer Friendly', value: '100%', icon: Users },
    { label: 'Science Based', value: 'Yes', icon: Award },
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
      <section className="relative py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center"
          >
            <h1 className="text-3xl sm:text-4xl md:text-6xl font-bold text-gray-900 mb-6">
              Sustainable Farming for{' '}
              <span className="text-green-600">Africa</span>
            </h1>
            <p className="text-lg sm:text-xl md:text-2xl text-gray-600 mb-8 max-w-3xl mx-auto">
              Assess your farm&apos;s environmental impact and get actionable insights 
              to improve sustainability and productivity
            </p>
            <div className="flex justify-center">
              <Link href="/assessment">
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="bg-green-600 hover:bg-green-700 text-white px-12 py-4 rounded-xl font-semibold text-lg flex items-center space-x-3 shadow-lg transition-colors duration-200"
                >
                  <Sprout className="w-6 h-6" />
                  <span>Start Farm Assessment</span>
                  <ArrowRight className="w-5 h-5" />
                </motion.button>
              </Link>
            </div>
            
            {/* Assessment Description */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="mt-8 max-w-4xl mx-auto"
            >
              <div className="bg-white rounded-xl p-8 shadow-lg border-2 border-green-200">
                <div className="flex items-center space-x-3 mb-4">
                  <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center">
                    <Sprout className="w-4 h-4 text-green-600" />
                  </div>
                  <h3 className="text-xl font-semibold text-gray-900">Comprehensive Farm Assessment</h3>
                </div>
                <p className="text-gray-600 mb-6">
                  Detailed Life Cycle Assessment (LCA) following ISO 14040/14044 standards, specifically designed 
                  for African agricultural systems. Get precise sustainability insights based on your actual 
                  farm management practices, cropping patterns, and regional conditions.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-gray-700">
                  <div className="space-y-2">
                    <p>✓ Complete farm system analysis</p>
                    <p>✓ Management practices evaluation</p>
                    <p>✓ Intercropping & crop rotation assessment</p>
                    <p>✓ Soil, water & pest management analysis</p>
                    <p>✓ Equipment & infrastructure evaluation</p>
                  </div>
                  <div className="space-y-2">
                    <p>✓ Regional benchmarking & comparisons</p>
                    <p>✓ Personalized recommendations</p>
                    <p>✓ 13 environmental impact categories</p>
                    <p>✓ Data quality assessment</p>
                    <p>✓ Actionable improvement strategies</p>
                  </div>
                </div>
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <p className="text-green-600 font-medium flex items-center">
                    <Clock className="w-4 h-4 mr-1" />
                    ⏱️ Complete assessment in 15-20 minutes
                  </p>
                </div>
              </div>
            </motion.div>
          </motion.div>
        </div>

        {/* Background decoration */}
        <div className="absolute inset-0 -z-10 overflow-hidden">
          <div className="absolute top-20 left-10 w-20 h-20 bg-green-200 rounded-full opacity-20 animate-pulse"></div>
          <div className="absolute top-40 right-20 w-16 h-16 bg-emerald-300 rounded-full opacity-20 animate-pulse delay-1000"></div>
          <div className="absolute bottom-20 left-20 w-24 h-24 bg-teal-200 rounded-full opacity-20 animate-pulse delay-2000"></div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 bg-white">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {stats.map((stat, index) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                className="text-center"
              >
                <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mx-auto mb-4">
                  <stat.icon className="w-6 h-6 text-green-600" />
                </div>
                <div className="text-3xl font-bold text-gray-900 mb-2">{stat.value}</div>
                <div className="text-gray-600">{stat.label}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <h2 className="text-2xl sm:text-3xl md:text-4xl font-bold text-gray-900 mb-4">
              Why Choose Green Means Go?
            </h2>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              Built specifically for African farmers with local expertise and research-backed methodology
            </p>
          </motion.div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 sm:gap-8">
            {features.map((feature, index) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: index * 0.2 }}
                className="bg-white rounded-xl p-6 shadow-lg hover:shadow-xl transition-shadow duration-300"
              >
                <div className={`w-12 h-12 ${feature.color} rounded-lg flex items-center justify-center mb-4`}>
                  <feature.icon className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-3">{feature.title}</h3>
                <p className="text-gray-600">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Impact Categories Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-white">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <h2 className="text-2xl sm:text-3xl md:text-4xl font-bold text-gray-900 mb-4">
              What We Measure
            </h2>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              Comprehensive environmental impact assessment covering all major sustainability factors
            </p>
          </motion.div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 sm:gap-8">
            {impacts.map((impact, index) => (
              <motion.div
                key={impact.title}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                className="text-center"
              >
                <div className="w-16 h-16 bg-gradient-to-r from-green-500 to-emerald-500 rounded-full flex items-center justify-center mx-auto mb-4">
                  <impact.icon className="w-8 h-8 text-white" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">{impact.title}</h3>
                <p className="text-gray-600 mb-2">{impact.description}</p>
                <span className="text-sm text-green-600 font-medium">{impact.value}</span>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-gradient-to-r from-green-600 to-emerald-600">
        <div className="max-w-4xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
          >
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-6">
              Ready to Assess Your Farm?
            </h2>
            <p className="text-xl text-green-100 mb-8">
              Get a comprehensive analysis of your farm&apos;s environmental impact and discover actionable ways to improve sustainability
            </p>
            <div className="flex justify-center">
              <Link href="/assessment">
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="bg-white text-green-600 hover:bg-gray-50 px-12 py-4 rounded-xl font-semibold text-xl flex items-center space-x-3 shadow-xl transition-colors duration-200"
                >
                  <Sprout className="w-6 h-6" />
                  <span>Start Assessment</span>
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
