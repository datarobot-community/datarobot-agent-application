// Copyright 2025 DataRobot, Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/**
 * Tests to validate that the paths and references mentioned in AGENTS.md
 * actually exist in the codebase.
 *
 * WHY THESE TESTS EXIST:
 * The AGENTS.md file provides instructions to AI agents and developers about
 * where to find and add code in the project. If the paths referenced in AGENTS.md
 * are incorrect or outdated, agents will fail to complete tasks correctly.
 * These tests ensure the documentation stays in sync with the actual project structure.
 */

import { describe, it, expect } from 'vitest';
import { existsSync, statSync } from 'fs';
import { resolve } from 'path';

const FRONTEND_ROOT = resolve(__dirname, '..');

describe('AGENTS.md path validation', () => {
  it('should have all paths referenced in AGENTS.md', () => {
    /**
     * Verify that the paths referenced in AGENTS.md actually exist.
     *
     * If this test fails, either the paths were moved/deleted and AGENTS.md needs
     * updating, or the paths need to be restored to match the documentation.
     */

    // Check that frontend_web/src/pages/ exists
    const pagesDir = resolve(FRONTEND_ROOT, 'src/pages');
    expect(existsSync(pagesDir), 'frontend_web/src/pages/ should exist').toBe(true);
    expect(statSync(pagesDir).isDirectory(), 'frontend_web/src/pages/ should be a directory').toBe(
      true
    );

    // Check that frontend_web/src/routesConfig.tsx exists
    const routesConfig = resolve(FRONTEND_ROOT, 'src/routesConfig.tsx');
    expect(existsSync(routesConfig), 'frontend_web/src/routesConfig.tsx should exist').toBe(true);
    expect(
      statSync(routesConfig).isFile(),
      'frontend_web/src/routesConfig.tsx should be a file'
    ).toBe(true);

    // Check that frontend_web/src/components/ exists
    const componentsDir = resolve(FRONTEND_ROOT, 'src/components');
    expect(existsSync(componentsDir), 'frontend_web/src/components/ should exist').toBe(true);
    expect(
      statSync(componentsDir).isDirectory(),
      'frontend_web/src/components/ should be a directory'
    ).toBe(true);

    // Check that frontend_web/src/components/ui/ exists
    const uiDir = resolve(FRONTEND_ROOT, 'src/components/ui');
    expect(existsSync(uiDir), 'frontend_web/src/components/ui/ should exist').toBe(true);
    expect(
      statSync(uiDir).isDirectory(),
      'frontend_web/src/components/ui/ should be a directory'
    ).toBe(true);

    // Check that frontend_web/src/api/ exists
    const apiDir = resolve(FRONTEND_ROOT, 'src/api');
    expect(existsSync(apiDir), 'frontend_web/src/api/ should exist').toBe(true);
    expect(statSync(apiDir).isDirectory(), 'frontend_web/src/api/ should be a directory').toBe(
      true
    );

    // Check that frontend_web/src/theme/ exists
    const themeDir = resolve(FRONTEND_ROOT, 'src/theme');
    expect(existsSync(themeDir), 'frontend_web/src/theme/ should exist').toBe(true);
    expect(statSync(themeDir).isDirectory(), 'frontend_web/src/theme/ should be a directory').toBe(
      true
    );
  });
});
