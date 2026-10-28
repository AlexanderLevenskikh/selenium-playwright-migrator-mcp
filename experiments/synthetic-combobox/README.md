# Synthetic ComboBox browser test

This is a PUBLIC, ARTIFICIAL mini-app for verifying the mechanics of a six-operation Playwright mapping template: open, wait for input, fill, wait for a unique option, click that option, confirm. It runs in Chromium via Microsoft.Playwright.NUnit and checks the resulting observable value. A second test intentionally omits confirmation and checks that the observable remains unchanged.

The HTML and selectors are entirely synthetic. No ArBilling source, authenticated environment, private hostnames, or customer-specific selectors are included. Passing this test **does not establish equivalent behavior on the private application**. That requires a trusted environment with its actual DOM, permissions, origin, data and backend.

Target-project compilation, browser tests, Core static mapping review, and production behavioral equivalence are separate evidence stages. The workflow checks actual 3/3 NUnit test execution via the TRX counters; it cannot pass vacuously with zero tests.
