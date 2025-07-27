import logging
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime

from core import models, schemas

logger = logging.getLogger(__name__)

class RulesEngine:
    def __init__(self, db: Session):
        self.db = db

    def get_contextual_suggestions(self, product_id: int) -> List[Dict[str, Any]]:
        """
        Retorna uma lista de opcionais e adicionais relevantes para um produto específico.
        """
        suggestions = []
        
        # Busca os opcionais ligados a este produto
        product = self.db.query(models.Product).filter(models.Product.id_produto == product_id).first()
        if product:
            for opcional in product.opcionais:
                suggestions.append({
                    "tipo": "opcional",
                    "id": opcional.id_opcional,
                    "nome": opcional.nome_opcional,
                    "preco": opcional.preco_adicional
                })
        
        logger.debug(f"Sugestões contextuais para produto {product_id}: {suggestions}")
        return suggestions

    def get_applicable_promotions(self, tenant_id: str, order_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Retorna uma lista de promoções aplicáveis com base no estado do pedido.
        """
        applicable_promotions = []
        
        promocoes = self.db.query(models.Promocao).filter(
            models.Promocao.tenant_id == tenant_id,
            models.Promocao.is_ativa == True
        ).all()
        
        for promocao in promocoes:
            # Aqui a lógica para avaliar condicao_json e acao_json seria implementada.
            # Por enquanto, vamos apenas retornar a descrição para a IA se a promoção estiver ativa.
            # A lógica de avaliação real seria mais complexa e dependeria da estrutura do JSON.
            
            # Exemplo simplificado: se a promoção tem uma descrição para a IA, consideramos aplicável
            if promocao.descricao_para_ia:
                applicable_promotions.append({
                    "id": promocao.id_promocao,
                    "nome": promocao.nome_promocao,
                    "descricao_para_ia": promocao.descricao_para_ia,
                    "condicao_json": promocao.condicao_json,
                    "acao_json": promocao.acao_json
                })
        
        logger.debug(f"Promoções aplicáveis para tenant {tenant_id} e order_state {order_state}: {applicable_promotions}")
        return applicable_promotions

    def evaluate_promotion_condition(self, condicao_json: Dict[str, Any], order_state: Dict[str, Any]) -> bool:
        """
        Avalia se a condição de uma promoção é atendida pelo estado do pedido.
        Esta é uma função placeholder e precisaria ser expandida para cada tipo de condição.
        """
        if not condicao_json:
            return True # Sem condição, sempre verdadeira
        
        # Exemplo: Condição baseada no dia da semana
        if condicao_json.get("tipo") == "DIA_SEMANA":
            dias_validos = condicao_json.get("dias", [])
            dia_atual = datetime.now().strftime("%a").upper() # Ex: "MON", "TUE"
            return dia_atual in dias_validos
        
        # Adicionar mais lógicas de condição aqui (VALOR_MINIMO, COMBO_PRODUTOS, etc.)
        
        return False # Condição não reconhecida ou não atendida

    def apply_promotion_action(self, acao_json: Dict[str, Any], current_price: float) -> float:
        """
        Aplica a ação de uma promoção ao preço atual.
        Esta é uma função placeholder e precisaria ser expandida para cada tipo de ação.
        """
        if not acao_json:
            return current_price
        
        # Exemplo: Desconto percentual
        if acao_json.get("tipo") == "DESCONTO_PERCENTUAL":
            percentual = acao_json.get("valor", 0)
            return current_price * (1 - percentual / 100)
        
        # Adicionar mais lógicas de ação aqui (DESCONTO_FIXO, BRINDE, etc.)
        
        return current_price # Ação não reconhecida ou não aplicada
