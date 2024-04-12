/* Copyright 2024 Marimo. All rights reserved. */
import {
  H1,
  H2,
  H3,
  H4,
  P,
  Lead,
  LargeText,
  SmallText,
  MutatedText,
} from "@/components/ui/typography";

export default {
  title: "Typography",
};

export const H1Story = {
  render: () => <H1>Taxing Laughter: The Joke Tax Chronicles</H1>,
  name: "H1",
};

export const H2Story = {
  render: () => <H2>Taxing Laughter: The Joke Tax Chronicles</H2>,
  name: "H2",
};

export const H3Story = {
  render: () => <H3>Taxing Laughter: The Joke Tax Chronicles</H3>,
  name: "H3",
};

export const H4Story = {
  render: () => <H4>Taxing Laughter: The Joke Tax Chronicles</H4>,
  name: "H4",
};

export const PStory = {
  render: () => <P>Taxing Laughter: The Joke Tax Chronicles</P>,
  name: "P",
};

export const ListUlStory = {
  render: () => (
    <ul className="my-6 ml-6 list-disc [&>li]:mt-2">
      <li>1st level of puns: 5 gold coins</li>
      <li>2nd level of jokes: 10 gold coins</li>
      <li>3rd level of one-liners : 20 gold coins</li>
    </ul>
  ),

  name: "List (UL)",
};

export const InlineCodeStory = {
  render: () => <H1>Taxing Laughter: The Joke Tax Chronicles</H1>,
  name: "Inline Code",
};

export const LeadStory = {
  render: () => <Lead>Taxing Laughter: The Joke Tax Chronicles</Lead>,
  name: "Lead",
};

export const LargeTextStory = {
  render: () => <LargeText>Taxing Laughter: The Joke Tax Chronicles</LargeText>,
  name: "LargeText",
};

export const SmallTextStory = {
  render: () => <SmallText>Taxing Laughter: The Joke Tax Chronicles</SmallText>,
  name: "SmallText",
};

export const MutatedTextStory = {
  render: () => (
    <MutatedText>Taxing Laughter: The Joke Tax Chronicles</MutatedText>
  ),
  name: "MutatedText",
};
