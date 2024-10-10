import { expect, test } from "@playwright/test";

test("user should be able to use duckduckgo search component", async ({
  page,
}) => {
  await page.goto("/");
  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });

  await page.waitForSelector('[id="new-project-btn"]', {
    timeout: 30000,
  });

  let modalCount = 0;
  try {
    const modalTitleElement = await page?.getByTestId("modal-title");
    if (modalTitleElement) {
      modalCount = await modalTitleElement.count();
    }
  } catch (error) {
    modalCount = 0;
  }

  while (modalCount === 0) {
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.getByTestId("blank-flow").click();
  await page.waitForSelector('[data-testid="extended-disclosure"]', {
    timeout: 30000,
  });
  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("duck");

  await page.waitForTimeout(1000);

  await page
    .locator('//*[@id="toolsDuckDuckGo Search"]')
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();
  await page.getByTitle("fit view").click();

  await page
    .getByTestId("popover-anchor-input-input_value")
    .fill("what is langflow?");

  await page.getByTestId("button_run_duckduckgo search").click();

  await page.getByTitle("fit view").click();

  await page.waitForSelector("text=built successfully", { timeout: 30000 });

  await page.waitForTimeout(1000);

  await page.getByTestId("output-inspection-data").first().click();

  await page.getByRole("gridcell").first().click();

  const searchResults = await page.getByPlaceholder("Empty").inputValue();
  expect(searchResults.length).toBeGreaterThan(10);
  expect(searchResults.toLowerCase()).toContain("langflow");
});
