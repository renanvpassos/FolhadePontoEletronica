import React from "react"
import ReactDOM from "react-dom/client"
import ComponentePonto from "./ComponentePonto" // Seu componente principal com o design
import { MantineProvider } from "@mantine/core" // Opcional: Se for usar o Mantine para o design

const root = ReactDOM.createRoot(document.getElementById("root"))

root.render(
  <React.StrictMode>
    {/* O Provider só é necessário se você usar bibliotecas de design como Mantine ou MaterialUI */}
    <MantineProvider withGlobalStyles withNormalizeCSS>
      <ComponentePonto />
    </MantineProvider>
  </React.StrictMode>
)
