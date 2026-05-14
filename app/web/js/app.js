/**
 * HireFlow AI — PWA frontend logic (Alpine.js).
 *
 * Single-file SPA: all views are toggled via `view` state, all data is
 * fetched from the same FastAPI backend that serves this HTML.
 */

const API = {
  jobs:        (params) => fetch('/jobs?' + new URLSearchParams(params)).then(r => r.json()),
  job:         (id)     => fetch(`/jobs/${id}`).then(r => r.json()),
  stats:       ()       => fetch('/stats').then(r => r.json()),
  sources:     ()       => fetch('/sources').then(r => r.json()),
  countries:   ()       => fetch('/countries').then(r => r.json()),
  startScrape: (body)   => fetch('/scrape', {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify(body),
                          }).then(async r => {
                              if (!r.ok) throw new Error((await r.json()).detail || `HTTP ${r.status}`);
                              return r.json();
                          }),
  scrapeStatus:()       => fetch('/scrape/status').then(r => r.json()),
};

const PAGE_SIZE = 50;

function hireflowApp() {
  return {
    /* ---------------- view state ---------------- */
    view: 'jobs',
    dark: localStorage.getItem('hf:dark') === '1',

    /* ---------------- data ---------------- */
    jobs: [],
    offset: 0,
    hasMore: false,
    loading: false,
    selectedJob: null,

    filters: {
      keyword: '',
      country: '',
      source: '',
      remote_only: false,
    },

    sources: [],
    countries: {},

    stats: null,

    scrapeForm: {
      keyword: 'developer',
      country: '',
      remote_only: false,
      sources: [],
    },
    scrapeRunning: false,
    scrapeMessage: '',
    scrapeError: false,

    /* ---------------- lifecycle ---------------- */
    async init() {
      this.applyDarkClass();
      this.registerServiceWorker();

      try {
        const [src, cty] = await Promise.all([API.sources(), API.countries()]);
        this.sources = src.sources || [];
        this.countries = cty.countries || {};
      } catch (e) {
        console.warn('Failed to load sources/countries', e);
      }

      this.reloadJobs();
    },

    registerServiceWorker() {
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').catch(err => {
          console.warn('SW registration failed:', err);
        });
      }
    },

    /* ---------------- theme ---------------- */
    toggleDark() {
      this.dark = !this.dark;
      localStorage.setItem('hf:dark', this.dark ? '1' : '0');
      this.applyDarkClass();
    },

    applyDarkClass() {
      document.documentElement.classList.toggle('dark', this.dark);
    },

    /* ---------------- view helpers ---------------- */
    viewTitle() {
      return {
        jobs:   'HireFlow AI',
        detail: 'Job details',
        stats:  'Statistics',
        scrape: 'New scrape',
      }[this.view] || 'HireFlow AI';
    },

    /* ---------------- jobs ---------------- */
    async reloadJobs() {
      this.offset = 0;
      this.jobs = [];
      await this.loadJobs();
    },

    async loadJobs() {
      if (this.loading) return;
      this.loading = true;
      try {
        const params = {
          limit: PAGE_SIZE,
          offset: this.offset,
          remote_only: this.filters.remote_only,
        };
        if (this.filters.keyword) params.keyword = this.filters.keyword;
        if (this.filters.country) params.country = this.filters.country;
        if (this.filters.source)  params.source  = this.filters.source;

        const data = await API.jobs(params);
        const items = Array.isArray(data) ? data : [];
        this.jobs = this.offset === 0 ? items : this.jobs.concat(items);
        this.hasMore = items.length === PAGE_SIZE;
      } catch (e) {
        console.error('loadJobs failed', e);
        this.hasMore = false;
      } finally {
        this.loading = false;
      }
    },

    async loadMoreJobs() {
      this.offset += PAGE_SIZE;
      await this.loadJobs();
    },

    openJob(job) {
      this.selectedJob = job;
      this.view = 'detail';
    },

    /* ---------------- stats ---------------- */
    async loadStats() {
      if (this.stats) return; // cached
      try {
        this.stats = await API.stats();
      } catch (e) {
        console.error('loadStats failed', e);
      }
    },

    topEntries(obj, n = 8) {
      if (!obj) return [];
      const entries = obj instanceof Array ? obj : Object.entries(obj);
      return entries
        .map(e => Array.isArray(e) ? e : [e[0], e[1]])
        .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))
        .slice(0, n);
    },

    barPct(obj, count) {
      if (!obj) return 0;
      const values = Object.values(obj).filter(v => typeof v === 'number');
      const max = values.length ? Math.max(...values) : 1;
      return max > 0 ? Math.round((count / max) * 100) : 0;
    },

    /* ---------------- scrape ---------------- */
    async startScrape() {
      this.scrapeMessage = '';
      this.scrapeError = false;
      this.scrapeRunning = true;
      try {
        const body = {
          keyword: this.scrapeForm.keyword.trim(),
          remote_only: this.scrapeForm.remote_only,
        };
        if (this.scrapeForm.country) body.country = this.scrapeForm.country;
        if (this.scrapeForm.sources.length) body.sources = this.scrapeForm.sources;

        const resp = await API.startScrape(body);
        this.scrapeMessage = resp.message || 'Scrape started';
        this.pollScrape();
      } catch (e) {
        this.scrapeError = true;
        this.scrapeMessage = `Failed to start scrape: ${e.message || e}`;
        this.scrapeRunning = false;
      }
    },

    async pollScrape() {
      const tick = async () => {
        try {
          const s = await API.scrapeStatus();
          if (!s.running) {
            this.scrapeRunning = false;
            this.scrapeMessage = 'Scrape finished. Refreshing job list…';
            this.stats = null; // invalidate stats cache
            await this.reloadJobs();
            this.scrapeMessage = 'Scrape finished. New jobs loaded.';
            return;
          }
        } catch (e) {
          // network blip — keep polling
        }
        setTimeout(tick, 3000);
      };
      setTimeout(tick, 2000);
    },

    /* ---------------- formatting ---------------- */
    formatDate(iso) {
      if (!iso) return '';
      try {
        const d = new Date(iso);
        if (isNaN(d.getTime())) return iso;
        return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
      } catch {
        return iso;
      }
    },
  };
}
