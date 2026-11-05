import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Recolección",
  description: "Prioridad de las calles y circuito del camión en el microcentro de CABA.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
