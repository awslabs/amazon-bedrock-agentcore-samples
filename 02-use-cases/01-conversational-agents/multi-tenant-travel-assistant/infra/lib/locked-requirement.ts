import * as fs from 'fs';
import * as path from 'path';

/** Repo root, independent of whether this runs from source or `dist/`. */
const REPO_ROOT = path.resolve(__dirname, __dirname.includes('dist') ? '../../..' : '../..');

/**
 * `<package>==<version>` exactly as a `uv.lock` resolved it.
 *
 * **Parsed rather than restated, because a version typed here is a second source of truth that only
 * looks correct.** `uv lock` would move on and this would not, and the drift shows up as a Lambda
 * running a library the tests never exercised — a class of bug that reproduces nowhere except in the
 * deployed function, and only for whoever cloned the sample after the upstream release.
 *
 * **Failing loudly if the lock cannot be read is the point.** A `catch` returning the bare package
 * name would restore the unpinned install this exists to remove, and would do it silently: `cdk
 * synth` would succeed, the bundle would build, and nothing would say which version shipped. An
 * unreadable lock is a repo problem, so it stops the synth.
 *
 * Two Lambdas are bundled with `pip install` rather than from a lock file, because both use CDK asset
 * bundling and neither has a wheel that `uv` needs to build: the tool functions add powertools, and
 * the conversation API adds uvicorn. Both read their version from the lock their own tests run
 * against — `tools/uv.lock` and `conversation-api/uv.lock` respectively — so `uv lock` in either
 * project flows through to the next deploy with no second place to remember.
 *
 * @param lockRelativePath the lock file, relative to the repo root
 * @param packageName the distribution name as it appears in the lock
 */
export function lockedRequirement(lockRelativePath: string, packageName: string): string {
  const lockPath = path.join(REPO_ROOT, lockRelativePath);
  const lock = fs.readFileSync(lockPath, 'utf8');
  // `uv.lock` is TOML, and this is a two-line regex rather than a TOML parse to keep `infra/` free of
  // a dependency added for one field. The shape is stable: `uv` writes `name` immediately followed by
  // `version` inside each `[[package]]` table. If that ever changes, the `throw` below is the signal.
  const match = lock.match(new RegExp(`name = "${packageName}"\\nversion = "([^"]+)"`));
  if (!match) {
    throw new Error(
      `could not read the ${packageName} version from ${lockRelativePath} — this bundle must ` +
        'install a pinned version, so synth fails rather than falling back to an unpinned install',
    );
  }
  return `${packageName}==${match[1]}`;
}
