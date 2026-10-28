using Microsoft.Playwright;
using Microsoft.Playwright.NUnit;
using NUnit.Framework;

namespace SyntheticCombobox;

/// <summary>
/// A deliberately artificial DOM exercising mechanics of reviewed target
/// statements. Not derived from or representative of the private ArBilling DOM.
/// </summary>
[TestFixture]
public sealed class ComboBoxBehaviorTests : PageTest
{
    private async Task ShowPage()
    {
        var fixture = Path.Combine(AppContext.BaseDirectory, "fixtures", "combobox.html");
        Assert.That(File.Exists(fixture), Is.True, "Synthetic fixture is missing");
        await Page.SetContentAsync(await File.ReadAllTextAsync(fixture));
    }

    private async Task<(ILocator Combo, ILocator Options)> SelectWithoutApply(string value)
    {
        // Six source-effect categories from a generic combo-box helper:
        // click -> wait -> fill -> wait-for-one -> option click -> apply click.
        // These selectors are fictional and solely test the structure.
        var combo = Page.Locator("[data-test-id=\"synthetic-combo\"] [data-tid=\"caption\"]");
        await combo.ClickAsync();

        var input = combo.Locator("xpath=.//*[contains(@data-test, 'headbox-search')]");
        await input.WaitForAsync(new() { State = WaitForSelectorState.Visible });
        await input.FillAsync(value);

        var options = combo.Locator("[data-test=\"menu-item\"]")
            .Filter(new() { HasTextString = value });
        await Expect(options).ToHaveCountAsync(1);
        await options.ClickAsync();
        return (combo, options);
    }

    [TestCase("alpha")]
    [TestCase("beta")]
    public async Task ConfirmedSelectionBecomesObservable(string value)
    {
        await ShowPage();
        var (combo, _) = await SelectWithoutApply(value);
        await combo.Locator("[data-test=\"apply-button\"]").ClickAsync();
        await Expect(Page.Locator("#selection")).ToHaveTextAsync(value);
    }

    [Test]
    public async Task MissingConfirmDoesNotSatisfyObservable()
    {
        await ShowPage();
        await SelectWithoutApply("alpha");
        // Deliberately omit the terminal "Apply" action. The target fixture
        // must remain unchanged, proving that missing confirmations matter.
        await Expect(Page.Locator("#selection")).ToHaveTextAsync("none");
    }
}
