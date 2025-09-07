import logging
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_, desc, text
from fastapi import HTTPException, status
from app.models.user import User
from app.models.article import Article, UserFavorite
from app.schemas.article import ArticleCreate, ArticleUpdate, ArticleSearchRequest

logger = logging.getLogger(__name__)

class ArticleService:
    @staticmethod
    def create_article(db: Session, article_data: ArticleCreate, user: User) -> Article:
        """記事を作成"""
        # URL重複チェック
        existing_article = db.query(Article).filter(Article.url == str(article_data.url)).first()
        if existing_article:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="この記事は既に登録されています"
            )
        
        # 記事作成
        db_article = Article(
            title=article_data.title,
            content=article_data.content,
            url=str(article_data.url),
            source=article_data.source,
            published_date=article_data.published_date,
            tags=article_data.tags or [],
            summary=article_data.summary,
            created_by=str(user.id)
        )
        
        db.add(db_article)
        db.commit()
        db.refresh(db_article)
        
        return db_article

    @staticmethod
    def get_article(db: Session, article_id: str, user: Optional[User] = None) -> Article:
        """記事IDで記事を取得"""
        try:
            # UUIDフォーマットの検証のみ行い、文字列として比較
            UUID(article_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid article ID format"
            )
        
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="記事が見つかりません"
            )
        
        return article

    @staticmethod
    def get_articles(
        db: Session, 
        search: ArticleSearchRequest, 
        user: Optional[User] = None
    ) -> Tuple[List[Article], int]:
        """記事一覧を取得（検索・フィルタリング・ページネーション対応）"""
        query = db.query(Article)
        
        # 検索クエリ（複数キーワード対応）
        if search.query:
            # キーワードを分割（スペース区切り）
            keywords = [kw.strip() for kw in search.query.split() if kw.strip()]
            
            if keywords:
                # 各キーワードがタイトル、内容、要約のいずれかに含まれる条件を作成
                search_conditions = []
                for keyword in keywords:
                    keyword_condition = or_(
                        Article.title.ilike(f"%{keyword}%"),
                        Article.content.ilike(f"%{keyword}%"),
                        Article.summary.ilike(f"%{keyword}%"),
                        Article.source.ilike(f"%{keyword}%")
                    )
                    search_conditions.append(keyword_condition)
                
                # AND/OR検索モードに応じて条件を結合
                if search.search_mode.lower() == "or":
                    # いずれかのキーワードが含まれる記事を検索（OR検索）
                    query = query.filter(or_(*search_conditions))
                else:
                    # すべてのキーワードが含まれる記事を検索（AND検索、デフォルト）
                    query = query.filter(and_(*search_conditions))
        
        # タグフィルター
        if search.tags:
            for tag in search.tags:
                query = query.filter(Article.tags.any(tag))
        
        # ソースフィルター
        if search.source:
            query = query.filter(Article.source.ilike(f"%{search.source}%"))
        
        # 日付フィルター
        if search.start_date:
            query = query.filter(Article.scraped_date >= search.start_date)
        
        if search.end_date:
            query = query.filter(Article.scraped_date <= search.end_date)
        
        # お気に入りフィルター
        if search.favorites_only and user:
            query = query.join(UserFavorite).filter(UserFavorite.user_id == user.id)
        
        # 総件数取得
        total = query.count()
        
        # ページネーション
        offset = (search.page - 1) * search.limit
        articles = query.order_by(desc(Article.scraped_date)).offset(offset).limit(search.limit).all()
        
        return articles, total

    @staticmethod
    def update_article(
        db: Session, 
        article_id: str, 
        article_data: ArticleUpdate, 
        user: User
    ) -> Article:
        """記事を更新（作成者または管理者のみ）"""
        article = ArticleService.get_article(db, article_id, user)
        
        # 権限チェック：管理者または作成者のみ
        if not user.is_admin and str(article.created_by) != str(user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="記事の更新権限がありません。作成者または管理者のみ実行できます"
            )
        
        # 更新データを適用
        update_data = article_data.model_dump(exclude_unset=True)
        logger.info(f"記事更新データ: {update_data}")
        logger.info(f"現在の記事データ: ID={article.id}, title={article.title}, url={article.url}")
        
        # URLが変更される場合、重複チェック
        if 'url' in update_data and update_data['url']:
            new_url = str(update_data['url'])
            if new_url != article.url:  # URLが実際に変更される場合のみチェック
                existing_article = db.query(Article).filter(
                    Article.url == new_url,
                    Article.id != article.id  # 自分自身は除外
                ).first()
                if existing_article:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="このURLは既に他の記事で使用されています"
                    )
        
        # データの個別設定（型変換エラーを防ぐため）
        for field, value in update_data.items():
            try:
                if field == 'tags':
                    if value is None:
                        setattr(article, field, [])
                    elif isinstance(value, list):
                        # リスト内の要素がすべて文字列であることを確認
                        clean_tags = [str(tag).strip() for tag in value if tag and str(tag).strip()]
                        setattr(article, field, clean_tags)
                    else:
                        logger.warning(f"Invalid tags format: {value}, type: {type(value)}")
                        continue
                elif field == 'title':
                    if not value or not str(value).strip():
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="タイトルは必須です"
                        )
                    setattr(article, field, str(value).strip())
                else:
                    setattr(article, field, value)
                logger.info(f"フィールド更新成功: {field} = {value}")
            except Exception as field_error:
                logger.error(f"フィールド '{field}' の更新エラー: {field_error}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"フィールド '{field}' の更新に失敗しました: {str(field_error)}"
                )
        
        try:
            db.commit()
            logger.info("データベースコミット成功")
        except Exception as commit_error:
            logger.error(f"データベースコミットエラー: {commit_error}")
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"データベース更新に失敗しました: {str(commit_error)}"
            )
        
        db.refresh(article)
        
        return article

    @staticmethod
    def delete_article(db: Session, article_id: str, user: User) -> bool:
        """記事を削除（作成者または管理者のみ）"""
        article = ArticleService.get_article(db, article_id, user)
        
        # 権限チェック：管理者または作成者のみ
        if not user.is_admin and str(article.created_by) != str(user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="記事の削除権限がありません。作成者または管理者のみ実行できます"
            )
        
        db.delete(article)
        db.commit()
        
        return True

    @staticmethod
    def toggle_favorite(db: Session, article_id: str, user: User) -> Tuple[bool, str]:
        """お気に入りの切り替え"""
        article = ArticleService.get_article(db, article_id, user)
        
        # 既存のお気に入りを検索
        existing_favorite = db.query(UserFavorite).filter(
            and_(
                UserFavorite.user_id == user.id,
                UserFavorite.article_id == article.id
            )
        ).first()
        
        if existing_favorite:
            # お気に入りを削除
            db.delete(existing_favorite)
            db.commit()
            return False, "お気に入りから削除しました"
        else:
            # お気に入りに追加
            new_favorite = UserFavorite(
                user_id=user.id,
                article_id=article.id
            )
            db.add(new_favorite)
            db.commit()
            return True, "お気に入りに追加しました"

    @staticmethod
    def is_favorite(db: Session, article_id: UUID, user_id: UUID) -> bool:
        """記事がユーザーのお気に入りかどうか判定"""
        favorite = db.query(UserFavorite).filter(
            and_(
                UserFavorite.user_id == user_id,
                UserFavorite.article_id == article_id
            )
        ).first()
        
        return favorite is not None

    @staticmethod
    def get_article_stats(db: Session) -> dict:
        """記事統計情報を取得"""
        total_articles = db.query(Article).count()
        
        # 今月追加された記事数（SQLite対応）
        from datetime import datetime, timezone
        import calendar
        
        now = datetime.now(timezone.utc)
        current_month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        monthly_articles = db.query(Article).filter(
            Article.scraped_date >= current_month_start
        ).count()
        
        # 人気のタグ（SQLite対応の簡易版）
        articles_with_tags = db.query(Article).filter(Article.tags.isnot(None)).all()
        tag_counts = {}
        for article in articles_with_tags:
            if article.tags:
                for tag in article.tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        popular_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # ソース別統計
        source_stats = db.query(
            Article.source,
            func.count().label('count')
        ).group_by(Article.source).order_by(desc('count')).limit(10).all()
        
        return {
            'total_articles': total_articles,
            'monthly_articles': monthly_articles,
            'popular_tags': popular_tags,
            'source_stats': [(row.source, row.count) for row in source_stats if row.source]
        }

    @staticmethod
    def get_all_tags(db: Session) -> List[str]:
        """全記事から重複なしでタグ一覧を取得"""
        articles_with_tags = db.query(Article).filter(Article.tags.isnot(None)).all()
        all_tags = set()
        
        for article in articles_with_tags:
            if article.tags:
                all_tags.update(article.tags)
        
        return sorted(list(all_tags))