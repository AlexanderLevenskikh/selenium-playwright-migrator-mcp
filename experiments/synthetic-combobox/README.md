# Synthetic ComboBox browser test

This is a PUBLIC, ARTIFICIAL mini-app for verifying the mechanics of a six-operation Playwright mapping template: open, wait for input, fill, wait for a unique option, click that option, confirm. It runs in Chromium via Microsoft.Playwright.NUnit and checks the resulting observable value. A second test intentionally omits confirmation and checks that the observable remains unchanged.

The HTML and selectors are entirely synthetic. No ArBilling source, authenticated environment, private hostnames, or customer-specific selectors are included. Passing this test **does not establish equivalent behavior on the private application**. That requires a trusted environment with its actual DOM, permissions, origin, data and backend.

Target-project compilation, browser tests, Core static mapping review, and production behavioral equivalence are separate evidence stages. The workflow checks actual 3/3 NUnit test execution via the TRX counters; it cannot pass vacuously with zero tests.

## Retry/reload Loader and table assertions

The additional `LoaderTableBehaviorTests` fixture intercepts a **fictional** URL with Playwright routing. On the first load it returns an error state; on reload it returns a visible ready marker and two table rows. A bounded two-attempt loader helper checks marker/loader state, reloads on error and fails after exhausting retries. A positive test checks the reload count and preserves both an exact text assertion and a substring assertion. A negative test deliberately returns an error on every request and confirms the retry policy fails rather than producing a false-green test.

The workflow requires **five executed NUnit tests total** (three ComboBox and two Loader/table), all passing; the negative control passes only if the loader throws and the ready marker is absent. These are source-independent synthetic controls. No Selenium project code or real ArBilling DOM is included. Even successful browser tests are not evidence of behavioral equivalence to the private test application.

### Evidence boundary

The loader synthetic test uses `System.TimeoutException` from `Locator.WaitForAsync` and an explicit exhaustion exception in the negative control so NUnit does not internally register an expected `Assert.Fail` as a failed test. This is a test-harness choice, not a claim that it reproduces the original Selenium assertion framework exception semantics.


## Preview.12 — negative assertion controls

Three additional Chromium/NUnit tests deliberately use wrong expectations against correctly loaded synthetic table rows and verify that equality, substring and negated substring assertions throw. The positive scenario also checks the non-inclusion of an absent substring. The workflow now fails unless all **eight** browser tests execute and pass. This provides independent mechanics only; no ArBilling DOM, origin, auth, retries or business assertions are validated.
