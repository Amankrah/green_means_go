'use client';

import Image from 'next/image';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  BookOpen,
  ExternalLink,
  Factory,
  Globe2,
  Sprout,
  Target,
  Users,
} from 'lucide-react';
import Layout from '@/components/Layout';

export const dynamic = 'force-dynamic';

const PRINCIPLES = [
  {
    icon: Target,
    title: 'Show the assumptions',
    body: 'A useful result is one people can inspect. Boundaries, inputs, and data quality belong beside the score.',
  },
  {
    icon: Globe2,
    title: 'Respect the region',
    body: 'Electricity, water pressure, yields, and practices change by place. The model should acknowledge that.',
  },
  {
    icon: Users,
    title: 'Design for the operator',
    body: 'Professional assessment should be usable by the people who hold the knowledge, not only by specialists.',
  },
];

const PATHWAYS = [
  {
    icon: Sprout,
    label: 'Farm pathway',
    title: 'From field activity to farm footprint',
    body: 'Record crop production, livestock, inputs, irrigation, energy, transport, and management choices in one workspace.',
    status: 'Available now',
  },
  {
    icon: Factory,
    label: 'Facility pathway',
    title: 'From incoming material to finished product',
    body: 'Trace energy, water, material losses, packaging, and processing steps across a production facility.',
    status: 'Available now',
  },
];

export default function AboutPage() {
  return (
    <Layout>
      <section className="relative overflow-hidden border-b border-line">
        <div className="field-grid absolute inset-0 opacity-50" aria-hidden="true" />
        <div className="relative mx-auto grid max-w-7xl gap-10 px-4 py-16 sm:px-6 sm:py-20 lg:grid-cols-[0.9fr_1.1fr] lg:items-end lg:px-8 lg:py-24">
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.65 }}
          >
            <p className="eyebrow">About / why this work exists</p>
            <h1 className="mt-5 font-display text-5xl font-light leading-[1.02] tracking-[-0.03em] text-ink sm:text-6xl lg:text-7xl">
              Sustainability claims need{' '}
              <span className="italic text-moss">better evidence.</span>
            </h1>
          </motion.div>
          <div className="max-w-xl lg:justify-self-end">
            <p className="text-xl leading-relaxed text-muted">
              Green Means Go helps farms and food facilities turn operational knowledge into a
              traceable life-cycle assessment without hiding the method behind the result.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link href="/signup" className="button-primary">Get started <ArrowRight className="h-4 w-4" /></Link>
              <Link href="/contact" className="button-secondary">Talk with the team</Link>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-surface">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 py-16 sm:px-6 sm:py-24 lg:grid-cols-[1.1fr_0.9fr] lg:px-8">
          <motion.figure
            initial={{ opacity: 0, y: 18 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.2 }}
            className="relative min-h-[420px] overflow-hidden rounded-[1.5rem] bg-ink lg:min-h-[610px]"
          >
            <Image
              src="/gmg-about-operations.webp"
              alt="A farmer and researcher reviewing operational records between crop fields"
              fill
              sizes="(min-width: 1024px) 55vw, 100vw"
              className="object-cover"
            />
            <figcaption className="absolute bottom-5 left-5 rounded-full border border-white/25 bg-ink/60 px-4 py-2 font-mono text-[0.62rem] uppercase tracking-[0.14em] text-white backdrop-blur-md">
              Records connect field decisions to facility impacts
            </figcaption>
          </motion.figure>
          <div className="flex flex-col justify-center lg:pl-12">
            <p className="eyebrow">Our mission</p>
            <h2 className="mt-4 font-display text-4xl font-light leading-tight text-ink sm:text-5xl">
              Make rigorous assessment practical at the point of decision.
            </h2>
            <p className="mt-7 text-lg leading-relaxed text-muted">
              Most environmental data starts with ordinary records: fertilizer rates, fuel use,
              electricity bills, yields, water, and transport. We bring those records into a
              consistent model so teams can see what drives impact and where better information is needed.
            </p>
            <blockquote className="mt-9 border-l-2 border-amber pl-6 font-display text-2xl font-light italic leading-relaxed text-ink">
              “The score is the summary. The real value is understanding what moved it.”
            </blockquote>
          </div>
        </div>
      </section>

      <section className="border-y border-line">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-24 lg:px-8">
          <p className="eyebrow">What guides the product</p>
          <div className="mt-5 grid gap-8 lg:grid-cols-[0.65fr_1.35fr]">
            <h2 className="font-display text-4xl font-light text-ink sm:text-5xl">
              Three principles,<br />used as tests.
            </h2>
            <div className="border-t border-line">
              {PRINCIPLES.map((principle, index) => {
                const Icon = principle.icon;
                return (
                  <motion.article
                    key={principle.title}
                    initial={{ opacity: 0, x: 12 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true, amount: 0.4 }}
                    transition={{ delay: index * 0.07 }}
                    className="grid gap-4 border-b border-line py-7 sm:grid-cols-[48px_0.8fr_1.2fr] sm:items-start"
                  >
                    <Icon className="h-6 w-6 text-moss" strokeWidth={1.6} />
                    <h3 className="font-display text-2xl text-ink">{principle.title}</h3>
                    <p className="leading-relaxed text-muted">{principle.body}</p>
                  </motion.article>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      <section className="bg-ink text-paper">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-24 lg:px-8">
          <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
            <div>
              <p className="eyebrow eyebrow-invert">Two connected pathways</p>
              <h2 className="mt-4 max-w-2xl font-display text-4xl font-light sm:text-5xl">
                Follow impact through the value chain.
              </h2>
            </div>
            <span className="font-mono text-[0.65rem] uppercase tracking-wider text-paper/50">Product scope</span>
          </div>
          <div className="mt-12 grid gap-px overflow-hidden rounded-2xl border border-paper/15 bg-paper/15 lg:grid-cols-2">
            {PATHWAYS.map((pathway) => {
              const Icon = pathway.icon;
              return (
                <article key={pathway.title} className="bg-ink p-7 sm:p-10">
                  <div className="flex items-center justify-between gap-4">
                    <Icon className="h-7 w-7 text-amber" strokeWidth={1.5} />
                    <span className="rounded-full border border-paper/20 px-3 py-1 font-mono text-[0.58rem] uppercase tracking-wider text-paper/60">
                      {pathway.status}
                    </span>
                  </div>
                  <p className="eyebrow eyebrow-invert mt-12">{pathway.label}</p>
                  <h3 className="mt-3 max-w-md font-display text-3xl font-light">{pathway.title}</h3>
                  <p className="mt-4 max-w-lg leading-relaxed text-paper/65">{pathway.body}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section className="border-b border-line bg-surface">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-20 sm:px-6 sm:py-24 lg:grid-cols-[0.7fr_1.3fr] lg:px-8">
          <div>
            <BookOpen className="h-7 w-7 text-moss" strokeWidth={1.5} />
            <p className="eyebrow mt-6">Research provenance</p>
          </div>
          <div>
            <h2 className="font-display text-4xl font-light leading-tight text-ink sm:text-5xl">
              Developed at McGill University.
            </h2>
            <p className="mt-6 max-w-3xl text-lg leading-relaxed text-muted">
              Green Means Go is developed at the Sustainable Agrifood Systems Engineering Lab
              (SASEL), where agricultural engineering, environmental science, and digital tools
              come together. The assessment approach is grounded in the principles of ISO 14040
              and ISO 14044.
            </p>
            <a
              href="https://sasellab.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-link mt-7"
            >
              Visit the SASEL lab <ExternalLink className="h-4 w-4" />
            </a>
          </div>
        </div>
      </section>

      <section className="bg-spruce text-paper">
        <div className="mx-auto max-w-5xl px-4 py-20 text-center sm:px-6 sm:py-24">
          <p className="eyebrow eyebrow-invert">Built in the open, improved with users</p>
          <h2 className="mx-auto mt-5 max-w-3xl font-display text-4xl font-light sm:text-6xl">
            Help shape a better assessment tool.
          </h2>
          <p className="mx-auto mt-6 max-w-xl text-lg text-paper/70">
            Green Means Go improves with the people who use it. Field feedback helps us sharpen the
            questions, regional data, and results.
          </p>
          <Link href="/contact" className="mt-9 inline-flex items-center justify-center gap-2 rounded-full bg-paper px-8 py-4 font-medium text-ink transition-colors hover:bg-white">
            Share feedback <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>
    </Layout>
  );
}

