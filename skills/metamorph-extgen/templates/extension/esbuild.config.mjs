/**
 * esbuild config for Metamorph extension
 * Builds all worker modules into a single worker.js
 */

import { build } from 'esbuild';
import { copyFileSync, mkdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';

const isWatch = process.argv.includes('--watch');
const outDir = join(__dirname, '..', 'dist');

async function buildExtension() {
  // Ensure output directories
  if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true });
  if (!existsSync(join(outDir, 'src', 'popup'))) mkdirSync(join(outDir, 'src', 'popup'), { recursive: true });
  if (!existsSync(join(outDir, 'config'))) mkdirSync(join(outDir, 'config'), { recursive: true });

  // Build service worker (bundles all worker modules)
  await build({
    entryPoints: [join(__dirname, 'src', 'worker', 'worker.js')],
    bundle: true,
    platform: 'browser',
    format: 'esm',
    target: 'chrome116',
    outfile: join(outDir, 'worker.js'),
    sourcemap: true,
    external: ['chrome'],
    define: {
      'globalThis': 'window',
    },
  });

  // Copy content script
  copyFileSync(
    join(__dirname, 'src', 'content', 'content.js'),
    join(outDir, 'content.js')
  );

  // Copy bridge (MAIN world)
  copyFileSync(
    join(__dirname, 'src', 'main-world', 'bridge.js'),
    join(outDir, 'bridge.js')
  );

  // Copy popup
  copyFileSync(
    join(__dirname, 'src', 'popup', 'popup.html'),
    join(outDir, 'popup.html')
  );
  copyFileSync(
    join(__dirname, 'src', 'popup', 'popup.js'),
    join(outDir, 'popup.js')
  );

  // Copy manifest (will be processed by generator)
  copyFileSync(
    join(__dirname, 'manifest.json'),
    join(outDir, 'manifest.json')
  );

  // Copy config
  copyFileSync(
    join(__dirname, 'config', 'origins.json'),
    join(outDir, 'config', 'origins.json')
  );

  console.log('Extension built to', outDir);
}

buildExtension().catch(() => process.exit(1));