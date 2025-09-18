import { useLocale } from "react-aria";

export const WithLocale = ({
  children,
}: {
  children: (locale: string | undefined) => React.ReactNode;
}) => {
  const { locale } = useLocale();
  return children(locale);
};
