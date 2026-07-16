'use client';

import Image from 'next/image';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  Bird,
  Droplets,
  Factory,
  Leaf,
  Mountain,
  Sprout,
  Users,
} from 'lucide-react';
import Layout from '@/components/Layout';

export const dynamic = 'force-dynamic';

const MEASURES = [
  { icon: Leaf, name: 'Climate', unit: 'kg CO₂-eq', blurb: 'Greenhouse gases across the full life cycle.' },
  { icon: Droplets, name: 'Water', unit: 'm³', blurb: 'Consumption weighted by local scarcity.' },
  { icon: Mountain, name: 'Land', unit: 'm²·yr', blurb: 'Occupation and pressure on soil systems.' },
  { icon: Bird, name: 'Biodiversity', unit: 'PDF·yr', blurb: 'Potential effects on surrounding species.' },
];

const ROLES = [
  {
    icon: Sprout,
    title: 'Farmers',
    body: 'See which inputs shape your footprint and keep a record you can compare season to season.',
  },
  {
    icon: Users,
    title: 'Advisors',
    body: 'Run consistent assessments across the farms you support without losing local context.',
  },
  {
    icon: Factory,
    title: 'Processors',
    body: 'Follow impacts from incoming material through energy, water, packaging, and finished product.',
  },
];

const STEPS = [
  ['01', 'Record the operation', 'Capture crops, materials, energy, water, transport, and management in a guided workspace.'],
  ['02', 'Trace the life cycle', 'The model connects foreground activity with region-aware background data and documented assumptions.'],
  ['03', 'Read what matters', 'Review the score, impact categories, major contributors, and practical next questions.'],
];

export default function HomePage() {
  return (
    <Layout>
      <section className="relative overflow-hidden border-b border-line">
        <div className="field-grid absolute inset-0 opacity-55" aria-hidden="true" />
        <div className="relative mx-auto max-w-[1440px] px-4 py-8 sm:px-6 sm:py-12 lg:px-8 lg:py-16">
          <div className="grid items-stretch gap-8 lg:grid-cols-[0.82fr_1.18fr] lg:gap-6">
            <motion.div
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.65 }}
              className="flex flex-col justify-center py-4 lg:pr-10"
            >
              <p className="eyebrow">Life-cycle assessment / field to facility</p>
              <h1 className="mt-5 max-w-2xl font-display text-[2.8rem] font-light leading-[0.98] tracking-[-0.035em] text-ink sm:text-6xl lg:text-[4.5rem]">
                Find the impact hidden in{' '}
                <span className="italic text-moss">everyday decisions.</span>
              </h1>
              <p className="mt-7 max-w-xl text-lg leading-relaxed text-muted sm:text-xl">
                Turn the real details of a farm or food facility into a transparent environmental
                assessment. It is grounded in ISO 14040/14044 principles and built for action.
              </p>
              <div className="mt-9 flex flex-col gap-3 sm:flex-row">
                <Link href="/signup" className="button-primary">
                  Start an assessment <ArrowRight className="h-4 w-4" />
                </Link>
                <a href="#how" className="button-secondary">See the method</a>
              </div>
              <div className="mt-10 flex items-center gap-3 border-t border-line pt-4 font-mono text-[0.66rem] uppercase tracking-[0.13em] text-muted">
                <span className="h-2 w-2 rounded-full bg-moss shadow-[0_0_0_4px_rgba(47,107,73,0.12)]" />
                Now live · Canada · Ghana · Nigeria
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, scale: 0.985 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.8, delay: 0.12 }}
              className="relative min-h-[470px] overflow-hidden rounded-[1.5rem] bg-ink shadow-[0_28px_70px_-34px_rgba(16,41,31,0.65)] lg:min-h-[620px]"
            >
              <Image
                src="/gmg-field-ledger-hero.webp"
                alt="Cultivated fields meeting a food processing facility"
                fill
                priority
                sizes="(min-width: 1024px) 58vw, 100vw"
                className="object-cover"
              />
              <div className="absolute inset-0 bg-[linear-gradient(180deg,transparent_35%,rgba(16,41,31,0.78)_100%)]" />
              <div className="absolute left-5 top-5 rounded-full border border-white/30 bg-ink/55 px-3 py-2 font-mono text-[0.62rem] uppercase tracking-[0.14em] text-white backdrop-blur-md sm:left-7 sm:top-7">
                Illustrative field record / SK-24
              </div>
              <div className="absolute bottom-5 left-5 right-5 grid gap-3 rounded-2xl border border-white/20 bg-paper/95 p-5 shadow-2xl backdrop-blur-md sm:bottom-7 sm:left-auto sm:right-7 sm:w-[390px] sm:p-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="eyebrow">Impact reading</p>
                    <p className="mt-1 font-display text-4xl font-light text-ink">0.28</p>
                  </div>
                  <span className="rounded-full bg-moss/10 px-3 py-1 font-mono text-[0.62rem] uppercase tracking-wider text-moss">
                    Lower band
                  </span>
                </div>
                <div>
                  <div className="impact-band relative h-2 rounded-full">
                    <motion.span
                      initial={{ left: '52%' }}
                      animate={{ left: '22%' }}
                      transition={{ duration: 1.1, delay: 0.65, ease: 'easeOut' }}
                      className="absolute -top-1 h-4 w-1 rounded-full bg-ink"
                    />
                  </div>
                  <div className="mt-2 flex justify-between font-mono text-[0.56rem] uppercase tracking-wider text-muted">
                    <span>Lower</span><span>Typical</span><span>Higher</span>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      <section className="border-b border-line bg-surface">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20 lg:px-8">
          <div className="grid gap-10 lg:grid-cols-[0.72fr_1.28fr]">
            <div>
              <p className="eyebrow">The measurement set</p>
              <h2 className="mt-4 max-w-md font-display text-4xl font-light leading-tight text-ink sm:text-5xl">
                One operation. Several environmental pressures.
              </h2>
            </div>
            <div className="grid border-l border-t border-line sm:grid-cols-2">
              {MEASURES.map((measure) => {
                const Icon = measure.icon;
                return (
                  <div key={measure.name} className="group border-b border-r border-line p-6 transition-colors hover:bg-paper sm:p-8">
                    <div className="flex items-start justify-between gap-4">
                      <Icon className="h-6 w-6 text-moss" strokeWidth={1.6} />
                      <span className="font-mono text-[0.62rem] uppercase tracking-wider text-muted">{measure.unit}</span>
                    </div>
                    <h3 className="mt-10 font-display text-2xl text-ink">{measure.name}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-muted">{measure.blurb}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      <section id="how" className="scroll-mt-24 bg-ink text-paper">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-24 lg:px-8">
          <div className="grid gap-12 lg:grid-cols-[0.65fr_1.35fr]">
            <div>
              <p className="eyebrow eyebrow-invert">How the record becomes evidence</p>
              <h2 className="mt-4 font-display text-4xl font-light leading-tight sm:text-5xl">
                Clear inputs.<br /><span className="italic text-amber">Traceable results.</span>
              </h2>
            </div>
            <ol className="border-t border-paper/20">
              {STEPS.map(([number, title, body]) => (
                <li key={number} className="grid gap-3 border-b border-paper/20 py-7 sm:grid-cols-[60px_0.7fr_1fr] sm:items-start sm:gap-6">
                  <span className="font-mono text-xs text-amber">{number}</span>
                  <h3 className="font-display text-2xl">{title}</h3>
                  <p className="leading-relaxed text-paper/65">{body}</p>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-24 lg:px-8">
        <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
          <div>
            <p className="eyebrow">Made for the people doing the work</p>
            <h2 className="mt-4 max-w-2xl font-display text-4xl font-light text-ink sm:text-5xl">
              A shared record across the food system.
            </h2>
          </div>
          <Link href="/about" className="text-link">Why we built it <ArrowRight className="h-4 w-4" /></Link>
        </div>
        <div className="mt-12 grid gap-4 md:grid-cols-3">
          {ROLES.map((role, index) => {
            const Icon = role.icon;
            return (
              <motion.article
                key={role.title}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.25 }}
                transition={{ duration: 0.45, delay: index * 0.08 }}
                className="rounded-2xl border border-line bg-surface p-7"
              >
                <Icon className="h-6 w-6 text-moss" strokeWidth={1.6} />
                <h3 className="mt-12 font-display text-2xl text-ink">{role.title}</h3>
                <p className="mt-3 leading-relaxed text-muted">{role.body}</p>
              </motion.article>
            );
          })}
        </div>
      </section>

      <section className="border-y border-line bg-surface">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-16 sm:px-6 sm:py-20 lg:grid-cols-[1fr_auto] lg:items-center lg:px-8">
          <div>
            <p className="eyebrow">Standards &amp; provenance</p>
            <h2 className="mt-4 max-w-3xl font-display text-3xl font-light text-ink sm:text-4xl">
              Research discipline, translated into a tool people can use.
            </h2>
            <p className="mt-4 max-w-2xl leading-relaxed text-muted">
              Developed at McGill University&apos;s Sustainable Agrifood Systems Engineering Lab,
              with a methodology grounded in ISO 14040 and ISO 14044 principles.
            </p>
          </div>
          <div className="grid grid-cols-2 divide-x divide-line border-y border-line py-4 font-mono text-[0.65rem] uppercase tracking-wider text-muted lg:min-w-[320px]">
            <div className="pr-8"><strong className="block font-display text-3xl font-light normal-case tracking-normal text-ink">ISO</strong>14040 / 14044</div>
            <div className="pl-8"><strong className="block font-display text-3xl font-light normal-case tracking-normal text-ink">13</strong>impact categories</div>
          </div>
        </div>
      </section>

      <section className="bg-spruce text-paper">
        <div className="mx-auto max-w-5xl px-4 py-20 text-center sm:px-6 sm:py-24">
          <p className="eyebrow eyebrow-invert">Your first field record starts here</p>
          <h2 className="mx-auto mt-5 max-w-3xl font-display text-4xl font-light leading-tight sm:text-6xl">
            Put evidence behind your next sustainability decision.
          </h2>
          <p className="mx-auto mt-6 max-w-xl text-lg text-paper/70">
            Create an account and run your first assessment in minutes.
          </p>
          <Link href="/signup" className="mt-9 inline-flex items-center justify-center gap-2 rounded-full bg-paper px-8 py-4 font-medium text-ink transition-colors hover:bg-white">
            Create your account <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>
    </Layout>
  );
}
