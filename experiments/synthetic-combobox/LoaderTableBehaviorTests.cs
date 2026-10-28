using Microsoft.Playwright;
using Microsoft.Playwright.NUnit;
using NUnit.Framework;

namespace SyntheticCombobox;

/// <summary>
/// Artificial retried loader + two row assertions. A synthetic routed HTML
/// response is used instead of any private backend. Successful execution only
/// proves this target-side mechanism under these artificial conditions.
/// </summary>
[TestFixture]
public sealed class LoaderTableBehaviorTests : PageTest
{
    private static readonly string ErrorPage = """
        <!doctype html><html lang="en"><body>
          <main id="root">
            <div data-test-id="load-error">Temporary loader error</div>
            <div data-test="table-loader">Loading...</div>
          </main>
        </body></html>
        """;

    private static readonly string RecoveredPage = """
        <!doctype html><html lang="en"><body>
          <main id="root">
            <div data-test-id="ready-marker">Ready</div>
            <section data-test="table">
              <div data-test="row">synthetic-100</div>
              <div data-test="row">General projects (synthetic)</div>
            </section>
          </main>
        </body></html>
        """;

    private async Task<Func<int>> RouteSyntheticPage(bool recoverOnReload)
    {
        var requests = 0;
        await Page.RouteAsync("**/synthetic-loader", async route =>
        {
            requests++;
            await route.FulfillAsync(new()
            {
                Status = 200,
                ContentType = "text/html",
                Body = recoverOnReload && requests >= 2 ? RecoveredPage : ErrorPage
            });
        });
        await Page.GotoAsync("https://example.invalid/synthetic-loader");
        return () => requests;
    }

    private async Task ValidateLoaderWithRetryAsync()
    {
        var error = Page.Locator("[data-test-id=\"load-error\"]");
        var loading = Page.Locator("[data-test=\"table-loader\"]");
        var marker = Page.Locator("[data-test-id=\"ready-marker\"]");

        var attempts = 0;
        while (attempts < 2)
        {
            try
            {
                if (await error.IsVisibleAsync())
                {
                    await Page.ReloadAsync();
                    await loading.WaitForAsync(new()
                    {
                        State = WaitForSelectorState.Hidden,
                        Timeout = 450
                    });
                }
                await marker.WaitForAsync(new()
                {
                    State = WaitForSelectorState.Visible,
                    Timeout = 450
                });
                await loading.WaitForAsync(new()
                {
                    State = WaitForSelectorState.Hidden,
                    Timeout = 450
                });
                break;
            }
            catch (System.TimeoutException)
            {
                attempts++;
                if (attempts == 2)
                    Assert.Fail("Synthetic page never became ready");
            }
        }
    }

    [Test]
    public async Task RetryReloadsAndThenBothTableAssertionsExecute()
    {
        var requestCount = await RouteSyntheticPage(recoverOnReload: true);
        await ValidateLoaderWithRetryAsync();
        Assert.That(requestCount(), Is.EqualTo(2), "Exactly one reload was expected");

        var rows = Page.Locator("[data-test=\"table\"] [data-test=\"row\"]");
        await Expect(rows.Nth(0)).ToHaveTextAsync("synthetic-100");
        await Expect(rows.Nth(1)).ToContainTextAsync("General projects");
    }

    [Test]
    public async Task PermanentErrorExhaustsRetryAndNeverClaimsReadiness()
    {
        var requestCount = await RouteSyntheticPage(recoverOnReload: false);
        var failed = false;
        try
        {
            await ValidateLoaderWithRetryAsync();
        }
        catch (AssertionException)
        {
            failed = true;
        }
        Assert.That(failed, Is.True, "The second timeout must fail, not silently return success");
        Assert.That(requestCount(), Is.EqualTo(3), "Two retries must reload the page twice");
        await Expect(Page.Locator("[data-test-id=\"ready-marker\"]")).ToHaveCountAsync(0);
    }
}
