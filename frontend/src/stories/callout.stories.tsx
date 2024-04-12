/* Copyright 2024 Marimo. All rights reserved. */
import { CalloutOutput } from "@/components/editor/output/CalloutOutput";

export default {
  title: "CalloutOutput",
  component: CalloutOutput,
};

export const Neutral = {
  render: () => (
    <CalloutOutput
      html="<p><b>NEUTRAL</b> CalloutOutput with <strong>HTML</strong></p>"
      kind="neutral"
    />
  ),

  name: "neutral",
};

export const Info = {
  render: () => (
    <CalloutOutput
      html="<p><b>INFO</b> CalloutOutput with <strong>HTML</strong></p>"
      kind="info"
    />
  ),

  name: "info",
};

export const Alert = {
  render: () => (
    <CalloutOutput
      html="<p><b>ALERT</b> CalloutOutput with <strong>HTML</strong></p>"
      kind="alert"
    />
  ),

  name: "alert",
};

export const Danger = {
  render: () => (
    <CalloutOutput
      html="<p><b>DANGER</b> CalloutOutput with <strong>HTML</strong></p>"
      kind="danger"
    />
  ),

  name: "danger",
};

export const Warn = {
  render: () => (
    <CalloutOutput
      html="<p><b>WARN</b> CalloutOutput with <strong>HTML</strong></p>"
      kind="warn"
    />
  ),

  name: "warn",
};

export const Success = {
  render: () => (
    <CalloutOutput
      html="<p><b>SUCCESS</b> CalloutOutput with <strong>HTML</strong></p>"
      kind="success"
    />
  ),

  name: "success",
};
