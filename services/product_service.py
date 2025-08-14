
import logging
from sqlalchemy.orm import Session
from thefuzz import process, fuzz
from typing import List, Optional

from core import models
from crud import product_crud
from core.schemas import BuscaDeProduto

logger = logging.getLogger(__name__)

class ProductService:
    """
    Camada de serviço para encapsular a lógica de negócio relacionada a produtos.
    """

    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.all_products_cache: Optional[List[models.Product]] = None

    def _get_all_products(self) -> List[models.Product]:
        """
        Busca todos os produtos do tenant e os armazena em cache na instância
        para evitar múltiplas chamadas ao banco de dados na mesma sessão.
        """
        if self.all_products_cache is None:
            logger.info(f"Buscando e cacheando todos os produtos para o tenant {self.tenant_id}")
            self.all_products_cache = product_crud.get_products_by_tenant(self.db, self.tenant_id)
        return self.all_products_cache

    def find_product_filtered(self, search_criteria: BuscaDeProduto, similarity_threshold: int = 80) -> List[models.Product]:
        """
        Encontra produtos com base em um critério de busca estruturado.
        Aplica filtros e depois busca por nome/similaridade.
        """
        logger.info(f"Iniciando busca filtrada de produto para o tenant '{self.tenant_id}' com critérios: {search_criteria}")

        # 1. Query base com filtro obrigatório de tenant
        query = self.db.query(models.Product).filter(models.Product.tenant_id == self.tenant_id)

        # 2. Aplicar filtros de categoria, se existirem
        if search_criteria.categorias:
            query = query.filter(models.Product.categoria_produto.in_(search_criteria.categorias))

        # 3. Aplicar filtros de inclusão de ingredientes, se existirem
        if search_criteria.ingredientes_incluir:
            for ingrediente in search_criteria.ingredientes_incluir:
                query = query.filter(models.Product.descricao_produto.ilike(f'%{ingrediente}%'))

        # 4. Aplicar filtros de exclusão de ingredientes, se existirem
        if search_criteria.ingredientes_excluir:
            for ingrediente in search_criteria.ingredientes_excluir:
                query = query.filter(models.Product.descricao_produto.not_ilike(f'%{ingrediente}%'))
        
        # 5. Executar a query filtrada para obter os candidatos
        candidate_products = query.all()
        
        # 6. Se não houver termos de busca gerais, retorna todos os candidatos que passaram nos filtros
        if not search_criteria.termos_gerais:
            logger.info(f"Nenhum termo geral de busca. Retornando {len(candidate_products)} produtos filtrados.")
            return candidate_products

        search_term = " ".join(search_criteria.termos_gerais)
        
        # Lógica de busca por nome/similaridade nos resultados já filtrados
        product_map = {p.nome_produto: p for p in candidate_products}
        
        if not product_map:
            return []

        # Tenta encontrar a melhor correspondência dentro dos candidatos
        best_match = process.extractOne(search_term, product_map.keys(), scorer=fuzz.token_set_ratio)
        
        if best_match and best_match[1] >= similarity_threshold:
            product_name = best_match[0]
            similarity_score = best_match[1]
            found_product = product_map[product_name]
            logger.info(f"Melhor correspondência encontrada nos produtos filtrados: '{found_product.nome_produto}' com similaridade de {similarity_score}%")
            return [found_product] # Retorna como lista para manter o tipo consistente
        
        logger.warning(f"Nenhum produto correspondente encontrado para '{search_term}' nos candidatos filtrados.")
        return []
