/* Copyright 2023 Marimo. All rights reserved. */
import { test, expect } from "@playwright/test";
import { getAppUrl } from "../playwright.config";

test.beforeEach(async ({ page }) => {
  const appUrl = getAppUrl("components.py");
  await page.goto(appUrl);
});

const pageHelper = async (page) => {
  return {
    selectBasicComponent: async (type: string) => {
      const select = await page.locator("#cell-1").locator("select");
      await select.selectOption({ label: type });
    },
    selectComplexComponent: async (type: string) => {
      const select = await page.locator("#cell-4").locator("select");
      await select.selectOption({ label: type });
    },
    verifyOutput: async (text: string) => {
      await expect(
        page.getByText(`The element's current value is ${text}`)
      ).toBeVisible();
    },
  };
};

test("page renders read only view in read mode", async ({ page }) => {
  // Filename is not visible
  await expect(page.getByText("components.py").last()).not.toBeVisible();
  // Has elements with class name 'controls'
  expect(await page.locator("#save-button").count()).toBe(0);

  // Can see output
  await expect(page.locator("h1").getByText("UI Elements")).toBeVisible();
});

test("button", async ({ page }) => {
  const helper = await pageHelper(page);
  await helper.selectBasicComponent("button");
  const element = page.locator("button").getByText("click me");

  // Verify is visible
  await expect(element).toBeVisible();
  // Verify output
  await helper.verifyOutput("0");
  // Click button
  await element.click();
  // Verify output
  await helper.verifyOutput("1");
});

test("checkbox", async ({ page }) => {
  const helper = await pageHelper(page);
  await helper.selectBasicComponent("checkbox");
  const element = page.getByText("check me");

  // Verify is visible
  await expect(element).toBeVisible();
  // Verify output
  await helper.verifyOutput("False");
  // Click checkbox
  await element.click();
  // Verify output
  await helper.verifyOutput("True");
  // Click checkbox
  await element.click();
  // Verify output
  await helper.verifyOutput("False");
});

test("date", async ({ page }) => {
  const helper = await pageHelper(page);
  await helper.selectBasicComponent("date");
  const element = page.getByRole("textbox");

  // Verify is visible
  await expect(element).toBeVisible();
  await element.fill("2020-01-20");
  // Verify output
  await helper.verifyOutput("2020-01-20");
});

test("dropdown", async ({ page }) => {
  const helper = await pageHelper(page);
  await helper.selectBasicComponent("dropdown");
  const element = page.locator("#cell-2").getByRole("combobox");

  // Verify is visible
  await expect(element).toBeVisible();
  // Verify output
  await helper.verifyOutput("None");
  // Select option
  await element.selectOption({ label: "b" });
  // Verify output
  await helper.verifyOutput("b");
});

test("file button", async ({ page }) => {
  const helper = await pageHelper(page);
  await helper.selectBasicComponent("file button");
  const element = page.getByRole("button", { name: "Upload", exact: true });
  // Verify is visible
  await expect(element).toBeVisible();
  // Verify output
  await helper.verifyOutput("None");
});

test("file area", async ({ page }) => {
  const helper = await pageHelper(page);
  await helper.selectBasicComponent("file area");
  const element = page.getByText("Drag and drop files here");
  // Verify is visible
  await expect(element).toBeVisible();
  // Verify output
  await helper.verifyOutput("None");
});

test("multiselect", async ({ page }) => {
  const helper = await pageHelper(page);
  await helper.selectBasicComponent("multiselect");
  let element = page.locator("marimo-multiselect div svg").last();

  // Verify is visible
  await expect(element).toBeVisible();
  // Verify output
  await helper.verifyOutput("");
  // Select option
  await element.click();
  await page.getByText("b", { exact: true }).click();
  // Verify output
  await helper.verifyOutput("b");
  // Select option
  element = page.locator("marimo-multiselect div svg").last();
  await element.click();
  await page.getByText("c", { exact: true }).click();
  // Verify output
  await helper.verifyOutput("b, c");
});

test("number", async ({ page }) => {
  const helper = await pageHelper(page);
  await helper.selectBasicComponent("number");
  const element = page.getByRole("spinbutton");

  // Verify is visible
  await expect(element).toBeVisible();
  // Verify output
  await helper.verifyOutput("1");
  // Select option
  await element.fill("5");
  // Verify output
  await helper.verifyOutput("5");
});

test("radio", async ({ page }) => {
  const helper = await pageHelper(page);
  await helper.selectBasicComponent("radio");
  const element = page.getByRole("radiogroup").getByText("a");

  // Verify is visible and selected
  await expect(element).toBeVisible();
  // Verify output
  await helper.verifyOutput("a");
  // Select option
  await page.getByRole("radiogroup").getByText("b").click();
  // Verify a is not selected
  // Verify output
  await helper.verifyOutput("b");
});

test("slider", async ({ page }) => {
  const helper = await pageHelper(page);
  await helper.selectBasicComponent("slider");
  const element = page.getByRole("slider");

  // Verify is visible and selected
  await expect(element).toBeVisible();
  // Verify output
  await helper.verifyOutput("1");
  // Move slider
  await element.dragTo(page.locator("marimo-slider"));
  // Verify output
  await helper.verifyOutput("6");
});

test("switch", async ({ page }) => {
  const helper = await pageHelper(page);
  await helper.selectBasicComponent("switch");
  const element = page.getByRole("switch");

  // Verify is visible
  await expect(element).toBeVisible();
  // Verify output
  await helper.verifyOutput("False");
  // Click checkbox
  await element.click();
  // Verify output
  await helper.verifyOutput("True");
  // Click checkbox
  await element.click();
  // Verify output
  await helper.verifyOutput("False");
});

test("table", async ({ page }) => {
  const helper = await pageHelper(page);
  await helper.selectBasicComponent("table");
  const element = page.getByText("Michael");

  // Verify is visible
  await expect(element).toBeVisible();
  // Click first checkbox to select all
  await page.getByRole("checkbox").first().click();
  await page.waitForTimeout(100); // Sleeps are not ideal
  const output = await page
    .locator("#cell-3")
    .locator(".marimo-json-output")
    .first()
    .innerText();
  expect(output).toMatch(
    `
[2 Items
0:{2 Items
"first_name":"Michael"
"last_name":"Scott"
}
1:{2 Items
"first_name":"Dwight"
"last_name":"Schrute"
}
]
  `.trim()
  );

  // Click second checkbox to remove first row
  await page.getByRole("checkbox").nth(1).click();
  await page.waitForTimeout(100); // Sleeps are not ideal
  const output2 = await page
    .locator("#cell-3")
    .locator(".marimo-json-output")
    .first()
    .innerText();
  expect(output2).toMatch(
    `
[1 Items
0:{2 Items
"first_name":"Dwight"
"last_name":"Schrute"
}
]
`.trim()
  );
});

test("text", async ({ page }) => {
  const helper = await pageHelper(page);
  await helper.selectBasicComponent("text");
  const element = page.getByRole("textbox");

  // Verify is visible
  await expect(element).toBeVisible();
  // Select option
  await element.fill("hello");
  // Verify output
  await helper.verifyOutput("hello");
});

test("text_area", async ({ page }) => {
  const helper = await pageHelper(page);
  await helper.selectBasicComponent("text_area");
  const element = page.getByRole("textbox");

  // Verify is visible
  await expect(element).toBeVisible();
  // Select option
  await element.fill("hello");
  // Verify output
  await helper.verifyOutput("hello");
});

test("complex - array", async ({ page }) => {
  const helper = await pageHelper(page);
  await helper.selectComplexComponent("array");

  // Check the elements
  const textbox = page.getByRole("textbox").first();
  const slider = page.getByRole("slider");
  const date = page.getByRole("textbox").last();
  // Verify they are visible
  await expect(textbox).toBeVisible();
  await expect(slider).toBeVisible();
  await expect(date).toBeVisible();
  // Fill
  await textbox.fill("hi marimo");
  await slider.dragTo(page.locator("marimo-slider").first());
  await date.fill("2020-01-20");
  // Verify output
  await page.waitForTimeout(100); // Sleeps are not ideal
  const output = await page
    .locator("#cell-6")
    .locator(".marimo-json-output")
    .first()
    .innerText();
  expect(output).toMatch(
    `
[3 Items
0:"hi marimo"
1:5
2:2020-01-20
]
`.trim()
  );
});

test("complex - batch", async ({ page }) => {
  const helper = await pageHelper(page);
  await helper.selectComplexComponent("batch");

  // Check the elements
  const textbox = page.getByRole("textbox").first();
  const date = page.getByRole("textbox").last();
  // Verify they are visible
  await expect(textbox).toBeVisible();
  await expect(date).toBeVisible();
  // Fill
  await textbox.fill("hi again marimo");
  await date.fill("2020-04-20");
  // Verify output
  await page.waitForTimeout(100); // Sleeps are not ideal
  const output = await page
    .locator("#cell-6")
    .locator(".marimo-json-output")
    .first()
    .innerText();
  expect(output).toMatch(
    `
{2 Items
"name":"hi again marimo"
"date":2020-04-20
}
`.trim()
  );
});

test("complex - dictionary", async ({ page }) => {
  const helper = await pageHelper(page);
  await helper.selectComplexComponent("dictionary");

  // Check the elements
  const textbox = page.getByRole("textbox").first();
  const buttons = page.locator("button:visible").getByText("click here");
  // Verify they are visible
  await expect(textbox).toBeVisible();
  await expect(buttons).toHaveCount(3);
  // Fill
  await textbox.fill("something!");
  // Click first button twice
  await buttons.first().click();
  await buttons.first().click();
  // Click last once
  await buttons.last().click();
  // Verify output
  await page.waitForTimeout(100); // Sleeps are not ideal
  const output = await page
    .locator("#cell-6")
    .locator(".marimo-json-output")
    .first()
    .innerText();
  expect(output).toMatch(
    `
{3 Items
"slider":1
"text":"something!"
"array":[3 Items
0:2
1:0
2:1
]
}
`.trim()
  );
});

test("complex - form", async ({ page }) => {
  const helper = await pageHelper(page);
  await helper.selectComplexComponent("form");

  // Check the elements
  const texteara = page.locator("textarea:visible");
  // Verify they are visible
  await expect(texteara).toBeVisible();
  // Verify no output
  await helper.verifyOutput("None");
  // Fill
  await texteara.fill("something!");
  // Verify output is still empty until submit
  await helper.verifyOutput("None");

  // Click submit
  await page.locator("button:visible").getByText("Submit").click();
  // Verify output
  await helper.verifyOutput("something!");
});

test("complex - reused in json", async ({ page }) => {
  const helper = await pageHelper(page);
  await helper.selectComplexComponent("reused-in-json");

  // Check the elements
  const textbox = page.getByRole("textbox");
  const number = page.getByRole("spinbutton");
  // Verify they are visible
  await expect(textbox).toHaveCount(2);
  await expect(number).toHaveCount(2);

  // Fill the first one
  await textbox.first().fill("hello");
  await number.first().fill("5");
  // Verify all have the same value
  await expect(textbox.last()).toHaveValue("hello");
  await expect(number.last()).toHaveValue("5");

  // Fill the last one
  await textbox.last().fill("world");
  await number.last().fill("10");
  // Verify all have the same value
  await expect(textbox.first()).toHaveValue("world");
  await expect(number.first()).toHaveValue("10");
});

test("complex - reused in markdown", async ({ page }) => {
  const helper = await pageHelper(page);
  await helper.selectComplexComponent("reused-in-markdown");

  // Check the elements
  const textbox = page.getByRole("textbox");
  const number = page.getByRole("spinbutton");
  // Verify they are visible
  await expect(textbox).toHaveCount(2);
  await expect(number).toHaveCount(2);

  // Fill the first one
  await textbox.first().fill("hello");
  await number.first().fill("5");
  // Verify all have the same value
  await expect(textbox.last()).toHaveValue("hello");
  await expect(number.last()).toHaveValue("5");

  // Fill the last one
  await textbox.last().fill("world");
  await number.last().fill("10");
  // Verify all have the same value
  await expect(textbox.first()).toHaveValue("world");
  await expect(number.first()).toHaveValue("10");
});
