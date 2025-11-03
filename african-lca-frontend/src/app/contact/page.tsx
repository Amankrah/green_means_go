'use client';

import React from 'react';
import { motion } from 'framer-motion';
import {
  Mail,
  MapPin,
  Phone,
  ExternalLink,
  Send,
  MessageCircle,
  Building2,
  Globe
} from 'lucide-react';
import Layout from '@/components/Layout';

export default function ContactPage() {
  const contactInfo = [
    {
      icon: Mail,
      title: 'Email',
      value: 'ebenezer.miezah@mcgill.ca',
      action: 'mailto:ebenezer.miezah@mcgill.ca',
      actionText: 'Send Email',
      color: 'text-green-600 bg-green-100',
    },
    {
      icon: Phone,
      title: 'Phone',
      value: '+1-514-398-7776',
      action: 'tel:+15143987776',
      actionText: 'Call Us',
      color: 'text-blue-600 bg-blue-100',
    },
    {
      icon: MapPin,
      title: 'Address',
      value: '2111 Lakeshore Road, Sainte-Anne-de-Bellevue, Quebec, Canada H9X 3V9',
      action: 'https://maps.google.com/?q=2111+Lakeshore+Road+Sainte-Anne-de-Bellevue+Quebec',
      actionText: 'View Map',
      color: 'text-purple-600 bg-purple-100',
      external: true,
    },
    {
      icon: Globe,
      title: 'SASEL Lab',
      value: 'Sustainable Agrifood Systems Engineering Lab',
      action: 'https://sasellab.com/',
      actionText: 'Visit Website',
      color: 'text-emerald-600 bg-emerald-100',
      external: true,
    },
  ];

  const quickLinks = [
    {
      icon: MessageCircle,
      title: 'General Inquiries',
      description: 'Questions about the platform, features, or how to get started',
      action: 'mailto:ebenezer.miezah@mcgill.ca?subject=Green%20Means%20Go%20-%20General%20Inquiry',
    },
    {
      icon: Send,
      title: 'Feedback & Suggestions',
      description: 'Share your experience and help us improve',
      action: 'mailto:ebenezer.miezah@mcgill.ca?subject=Green%20Means%20Go%20-%20Feedback',
    },
    {
      icon: Building2,
      title: 'Partnership Opportunities',
      description: 'Collaborate with us on research or implementation',
      action: 'mailto:ebenezer.miezah@mcgill.ca?subject=Green%20Means%20Go%20-%20Partnership',
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
              <div className="flex justify-center mb-6">
                <div className="bg-white/20 backdrop-blur-sm rounded-full p-4">
                  <Mail className="w-12 h-12 text-white" />
                </div>
              </div>
              <h1 className="text-4xl sm:text-5xl font-bold mb-6">
                Get in Touch
              </h1>
              <p className="text-xl text-green-50 max-w-2xl mx-auto mb-8">
                Have questions or feedback? We&apos;d love to hear from you.
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

        {/* Quick Contact Actions */}
        <section className="py-16 bg-green-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
              className="text-center mb-12"
            >
              <h2 className="text-3xl font-bold text-gray-900 mb-4">
                How Can We Help?
              </h2>
              <p className="text-lg text-gray-600">
                Choose a category to get started
              </p>
            </motion.div>

            <div className="grid md:grid-cols-3 gap-6 mb-12">
              {quickLinks.map((link, index) => (
                <motion.a
                  key={link.title}
                  href={link.action}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.6, delay: index * 0.1 }}
                  className="bg-white rounded-xl p-6 shadow-lg hover:shadow-xl transition-all duration-300 group cursor-pointer"
                >
                  <div className="flex items-start space-x-4">
                    <div className="bg-green-100 rounded-lg p-3 flex-shrink-0 group-hover:bg-green-200 transition-colors">
                      <link.icon className="w-6 h-6 text-green-600" />
                    </div>
                    <div className="flex-1">
                      <h3 className="text-lg font-semibold text-gray-900 mb-2 group-hover:text-green-600 transition-colors">
                        {link.title}
                      </h3>
                      <p className="text-sm text-gray-600">
                        {link.description}
                      </p>
                    </div>
                  </div>
                </motion.a>
              ))}
            </div>
          </div>
        </section>

        {/* Contact Information */}
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
                Contact Information
              </h2>
              <p className="text-lg text-gray-600">
                Reach out to us through any of these channels
              </p>
            </motion.div>

            <div className="grid md:grid-cols-2 gap-6 max-w-5xl mx-auto">
              {contactInfo.map((info, index) => (
                <motion.div
                  key={info.title}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.6, delay: index * 0.1 }}
                  className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-xl p-6 border border-green-100"
                >
                  <div className="flex items-start space-x-4">
                    <div className={`rounded-lg p-3 flex-shrink-0 ${info.color}`}>
                      <info.icon className="w-6 h-6" />
                    </div>
                    <div className="flex-1">
                      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
                        {info.title}
                      </h3>
                      <p className="text-gray-900 mb-3 break-words">
                        {info.value}
                      </p>
                      <a
                        href={info.action}
                        target={info.external ? '_blank' : undefined}
                        rel={info.external ? 'noopener noreferrer' : undefined}
                        className="inline-flex items-center space-x-1 text-green-600 hover:text-green-700 font-medium text-sm transition-colors"
                      >
                        <span>{info.actionText}</span>
                        {info.external && <ExternalLink className="w-4 h-4" />}
                      </a>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        {/* SASEL Lab Section */}
        <section className="py-16 bg-gradient-to-br from-green-600 to-emerald-600 text-white">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
              className="text-center"
            >
              <h2 className="text-3xl font-bold mb-6">
                Developed at SASEL Lab
              </h2>
              <p className="text-xl text-green-50 mb-8 leading-relaxed">
                Green Means Go is developed at the Sustainable Agrifood Systems Engineering Lab 
                at McGill University. Our team is dedicated to advancing sustainable food systems 
                through innovative research and practical tools.
              </p>
              <a
                href="https://sasellab.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center space-x-2 bg-white text-green-600 px-8 py-4 rounded-lg font-semibold hover:bg-green-50 transition-colors duration-200 shadow-lg"
              >
                <span>Visit SASEL Lab</span>
                <ExternalLink className="w-5 h-5" />
              </a>
            </motion.div>
          </div>
        </section>

        {/* Beta Feedback CTA */}
        <section className="py-12 bg-orange-50 border-y border-orange-200">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <div className="inline-flex items-center space-x-2 bg-orange-100 px-4 py-2 rounded-full border border-orange-300 mb-4">
              <span className="text-2xl">💡</span>
              <span className="font-bold text-orange-600">BETA FEEDBACK</span>
            </div>
            <h3 className="text-2xl font-bold text-gray-900 mb-4">
              Help Us Improve
            </h3>
            <p className="text-lg text-gray-700 mb-6 max-w-2xl mx-auto">
              As we&apos;re in beta, your feedback is invaluable. Found a bug? Have a feature suggestion? 
              We want to hear from you!
            </p>
            <a
              href="mailto:ebenezer.miezah@mcgill.ca?subject=Green%20Means%20Go%20-%20Beta%20Feedback"
              className="inline-flex items-center space-x-2 bg-orange-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-orange-700 transition-colors duration-200"
            >
              <Send className="w-5 h-5" />
              <span>Share Your Feedback</span>
            </a>
          </div>
        </section>
      </div>
    </Layout>
  );
}

