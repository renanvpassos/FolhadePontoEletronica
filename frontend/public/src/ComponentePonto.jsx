import React, { useEffect } from "react"
import { Streamlit, withStreamlitConnection } from "streamlit-component-lib"
import { Button, Card, Text } from "@mantine/core" // Exemplo usando Mantine

function ComponentePonto({ args }) {
  // 1. Recebe os dados enviados pelo Python através do 'args'
  const { opcao, horarioExistente } = args;

  useEffect(() => {
    // Ajusta a altura do componente dinamicamente no Streamlit
    Streamlit.setFrameHeight();
  }, []);

  const lidarComClique = () => {
    // 2. Retorna a ação para o Python executar o salvamento
    Streamlit.setComponentValue({ acao: "registrar", horario: new Date().toISOString() });
  };

  return (
    <Card shadow="sm" padding="lg" radius="md" withBorder>
      <Text weight={500}>Registro de {opcao}</Text>
      {horarioExistente ? (
        <Text color="green">Já registrado às {horarioExistente}</Text>
      ) : (
        <Button onClick={lidarComClique} color="blue">Bater Ponto</Button>
      )}
    </Card>
  );
}

export default withStreamlitConnection(ComponentePonto);
