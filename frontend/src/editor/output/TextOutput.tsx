/* Copyright 2023 Marimo. All rights reserved. */

interface Props {
  text: string;
  className?: string;
}

export const TextOutput = ({ text, className }: Props): JSX.Element => {
  return <span className={`${className} text-plain`}>{text}</span>;
};
