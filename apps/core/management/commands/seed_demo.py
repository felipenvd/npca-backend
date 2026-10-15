from collections import defaultdict
from datetime import time, timedelta

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.images import validate_content_image
from apps.courses.models import Course, CourseTranslation
from apps.events.models import Event, EventTranslation
from apps.labcompap.models import LabEquipment, LabGalleryImage
from apps.news.models import News, NewsTranslation
from apps.projects.models import Project, ProjectTeamMember, ProjectTranslation
from apps.publications.models import Publication, PublicationAuthor, PublicationTranslation
from apps.researchers.models import Researcher, ResearcherTranslation

IMAGE_ROOT = settings.BASE_DIR / "scripts" / "seed" / "labcompap" / "media" / "gallery"
LANGUAGES = ("pt-br", "en")
TOPICS = (
    ("Inteligência artificial aplicada", "Applied artificial intelligence"),
    ("Monitoramento ambiental", "Environmental monitoring"),
    ("Tecnologia para a agricultura", "Technology for agriculture"),
    ("Ciência de dados abertos", "Open data science"),
    ("Educação e inclusão digital", "Education and digital inclusion"),
)


def content(topic: tuple[str, str], language: str, number: int) -> dict[str, str]:
    title = f"[DEMO] {topic[language == 'en']} {number:02d}"
    summary = (
        "Conteúdo fictício para testar o admin e o site do NPCA. "
        "As imagens são ilustrativas e não representam esta iniciativa."
        if language == "pt-br"
        else "Fictional content for testing the NPCA admin and website. "
        "Images are illustrative and do not represent this initiative."
    )
    body = (
        "<h2>Sobre este exemplo</h2><p>Este registro permite testar edição, "
        "traduções, imagens, links e publicação de conteúdo.</p>"
        "<ul><li>Pesquisa aplicada</li><li>Formação acadêmica</li>"
        "<li>Resultados demonstrativos</li></ul>"
        if language == "pt-br"
        else "<h2>About this example</h2><p>This record lets you test editing, "
        "translations, images, links and content publishing.</p>"
        "<ul><li>Applied research</li><li>Academic training</li>"
        "<li>Demonstration results</li></ul>"
    )
    return {
        "title": title,
        "summary": summary,
        "body_html": f"<p>{summary}</p>{body}",
        "seo_title": title[:70],
        "seo_description": summary[:160],
    }


class Command(BaseCommand):
    help = "Preenche todas as áreas do admin com exemplos bilíngues, apenas em desenvolvimento."

    def handle(self, *args, **options) -> None:
        if not settings.DEBUG:
            raise CommandError("seed_demo só pode ser executado em desenvolvimento (DEBUG=True).")

        self.images = self._load_images()
        self.created_files = []
        self.counts = defaultdict(lambda: [0, 0])
        self.today = timezone.localdate()
        try:
            with transaction.atomic():
                self._accounts()
                researchers = self._researchers()
                projects = self._projects(researchers)
                self._news()
                self._events()
                self._publications(researchers, projects)
                self._courses()
                self._labcompap()
        except Exception as error:
            for storage, name in reversed(self.created_files):
                try:
                    storage.delete(name)
                except OSError as cleanup_error:
                    self.stderr.write(f"Não foi possível remover {name}: {cleanup_error}")
            if isinstance(error, OSError | ValidationError):
                raise CommandError(
                    f"Não foi possível criar os exemplos: {error}. "
                    "Confira as validações e se MEDIA_ROOT aponta para uma pasta gravável."
                ) from error
            raise

        for label, (created, skipped) in self.counts.items():
            self.stdout.write(f"{label}: {created} criados, {skipped} já existentes.")
        self.stdout.write(
            self.style.SUCCESS(
                "Seed de demonstração concluído. Registros existentes foram preservados. "
                "As contas DEMO são inativas e não possuem senha utilizável."
            )
        )

    @staticmethod
    def _load_images() -> list[bytes]:
        images = []
        for number in range(1, 10):
            name = f"image_{number:02d}.webp"
            try:
                data = (IMAGE_ROOT / name).read_bytes()
                validate_content_image(ContentFile(data, name=name), label=name)
            except (OSError, ValidationError) as error:
                raise CommandError(
                    f"Não foi possível carregar a imagem de seed {name}: {error}"
                ) from error
            images.append(data)
        return images

    def _record(self, model, lookup: dict, values: dict):
        instance, created = model.objects.get_or_create(**lookup, defaults=values)
        self.counts[str(model._meta.verbose_name_plural)][not created] += 1
        return instance, created

    def _image(self, instance, field_name: str, number: int) -> None:
        field = getattr(instance, field_name)
        field.save(
            f"demo-{number:02d}.webp",
            ContentFile(self.images[(number - 1) % len(self.images)]),
            save=False,
        )
        self.created_files.append((field.storage, field.name))

    @staticmethod
    def _save(instance) -> None:
        instance.full_clean()
        instance.save()

    def _publish(self, instance, status: str = "published") -> None:
        instance.validate_for_publication()
        instance.status = status
        self._save(instance)

    def _translations(self, instance, model, relation: str, slug: str, topic, number) -> None:
        for language in LANGUAGES:
            values = content(topic, language, number)
            self._save(model(**{relation: instance}, language=language, slug=slug, **values))

    def _accounts(self) -> None:
        groups = []
        for label, actions in (("Editores", ("view", "add", "change")), ("Leitores", ("view",))):
            group, created = self._record(Group, {"name": f"[DEMO] {label}"}, {})
            if created:
                group.permissions.set(
                    Permission.objects.filter(
                        content_type__app_label__in=(
                            "news",
                            "researchers",
                            "projects",
                            "publications",
                            "events",
                            "courses",
                            "labcompap",
                        ),
                        codename__regex=rf"^({'|'.join(actions)})_",
                    )
                )
            groups.append(group)
        users = []
        for number, group in enumerate(groups, start=1):
            user, created = self._record(
                User,
                {"email": f"demo{number}@npca.example"},
                {"first_name": "DEMO", "last_name": f"Conta {number}", "is_active": False},
            )
            if created:
                user.set_unusable_password()
                self._save(user)
                user.groups.add(group)
            users.append(user)
        self.editor = users[0]

    def _researchers(self) -> list[Researcher]:
        researchers = []
        categories = Researcher.AcademicCategory.values
        for number in range(1, 7):
            slug = f"demo-pesquisador-{number:02d}"
            researcher, created = self._record(
                Researcher,
                {"public_email": f"pesquisador-demo{number}@npca.example"},
                {
                    "full_name": f"[DEMO] Pesquisador {number:02d}",
                    "academic_category": categories[(number - 1) % len(categories)],
                    "display_order": number,
                    "created_by": self.editor,
                    "updated_by": self.editor,
                },
            )
            if created:
                self._image(researcher, "photo", number)
                for language in LANGUAGES:
                    values = content(TOPICS[(number - 1) % len(TOPICS)], language, number)
                    self._save(
                        ResearcherTranslation(
                            researcher=researcher,
                            language=language,
                            slug=slug,
                            research_area=TOPICS[(number - 1) % len(TOPICS)][language == "en"],
                            biography_html=values["body_html"],
                            seo_title=values["seo_title"],
                            seo_description=values["seo_description"],
                        )
                    )
                researcher.validate_for_activation()
                researcher.is_active = number <= 5
                self._save(researcher)
            researchers.append(researcher)
        return researchers

    def _projects(self, researchers) -> list[Project]:
        projects = []
        for number, topic in enumerate(TOPICS, start=1):
            slug = f"demo-projeto-{number:02d}"
            project, created = self._record(
                Project,
                {"translations__language": "pt-br", "translations__slug": slug},
                {
                    "situation": Project.Situation.values[(number - 1) % 3],
                    "start_date": self.today - timedelta(days=180),
                    "end_date": self.today - timedelta(days=30) if number == 3 else None,
                    "coordinator": researchers[0],
                    "funding": "Financiamento fictício de teste",
                    "partners": "[DEMO] Parceiro acadêmico\n[DEMO] Parceiro tecnológico",
                    "website_url": f"https://example.org/npca-demo/projects/{number}",
                    "repository_url": f"https://example.org/npca-demo/repositories/{number}",
                    "is_featured": number <= 3,
                    "display_order": number,
                    "created_by": self.editor,
                    "updated_by": self.editor,
                },
            )
            if created:
                self._image(project, "cover", number)
                project.cover_credit = "Imagem ilustrativa do pacote de seed do LabCompAp"
                self._translations(project, ProjectTranslation, "project", slug, topic, number)
                for researcher in researchers[1:4]:
                    self._save(ProjectTeamMember(project=project, researcher=researcher))
                self._publish(project, self._status(number, 3))
            projects.append(project)
        return projects

    @staticmethod
    def _status(number: int, published: int) -> str:
        if number <= published:
            return "published"
        return "draft" if number == published + 1 else "archived"

    def _news(self) -> None:
        for number in range(1, 16):
            slug = f"demo-noticia-{number:02d}"
            news, created = self._record(
                News,
                {"translations__language": "pt-br", "translations__slug": slug},
                {"created_by": self.editor, "updated_by": self.editor},
            )
            if created:
                self._image(news, "cover", number)
                news.cover_credit = "Imagem ilustrativa do pacote de seed do LabCompAp"
                self._translations(
                    news,
                    NewsTranslation,
                    "news",
                    slug,
                    TOPICS[(number - 1) % 5],
                    number,
                )
                news.published_at = timezone.now() - timedelta(days=number)
                self._publish(news, self._status(number, 13))

    def _events(self) -> None:
        for number, event_type in enumerate(Event.EventType.values, start=1):
            slug = f"demo-evento-{number:02d}"
            modality = Event.Modality.values[(number - 1) % 3]
            start = self.today + timedelta(days=number * 7)
            if number == 4:
                start = self.today - timedelta(days=14)
            elif number == 5:
                start = self.today - timedelta(days=1)
            event, created = self._record(
                Event,
                {"translations__language": "pt-br", "translations__slug": slug},
                {
                    "event_type": event_type,
                    "modality": modality,
                    "schedule_status": Event.ScheduleStatus.values[(number - 1) % 3]
                    if number <= 3
                    else Event.ScheduleStatus.COMPLETED
                    if number == 4
                    else Event.ScheduleStatus.SCHEDULED,
                    "start_date": start,
                    "end_date": self.today + timedelta(days=1) if number == 5 else start,
                    "is_all_day": number in (4, 5),
                    "start_time": None if number in (4, 5) else time(9),
                    "end_time": None if number in (4, 5) else time(12),
                    "online_url": f"https://example.org/npca-demo/meetings/{number}"
                    if modality != Event.Modality.IN_PERSON
                    else "",
                    "registration_url": f"https://example.org/npca-demo/register/{number}",
                    "display_order": number,
                    "created_by": self.editor,
                    "updated_by": self.editor,
                },
            )
            if created:
                self._image(event, "cover", number)
                event.cover_credit = "Imagem ilustrativa do pacote de seed do LabCompAp"
                for language in LANGUAGES:
                    values = content(TOPICS[(number - 1) % 5], language, number)
                    self._save(
                        EventTranslation(
                            event=event,
                            language=language,
                            slug=slug,
                            **values,
                            location_name="[DEMO] LabCompAp" if modality != "online" else "",
                            location_address="Endereço fictício para teste"
                            if modality != "online"
                            else "",
                            cover_alt_text="Imagem ilustrativa do laboratório"
                            if language == "pt-br"
                            else "Illustrative laboratory image",
                        )
                    )
                self._publish(event, self._status(number, 6))

    def _publications(self, researchers, projects) -> None:
        for number in range(1, 7):
            publication, created = self._record(
                Publication,
                {"external_url": f"https://example.org/npca-demo/publications/{number}"},
                {
                    "year": self.today.year - (number - 1) % 3,
                    "venue": "[DEMO] Simpósio de Computação Aplicada",
                    "project": projects[(number - 1) % 3],
                    "display_order": number,
                    "created_by": self.editor,
                    "updated_by": self.editor,
                },
            )
            if created:
                self._image(publication, "cover", number)
                publication.cover_credit = "Imagem ilustrativa do pacote de seed do LabCompAp"
                for language in LANGUAGES:
                    values = content(TOPICS[(number - 1) % 5], language, number)
                    self._save(
                        PublicationTranslation(
                            publication=publication,
                            language=language,
                            title=values["title"],
                            abstract=values["summary"],
                            cover_alt_text="Imagem ilustrativa do laboratório"
                            if language == "pt-br"
                            else "Illustrative laboratory image",
                            seo_title=values["seo_title"],
                            seo_description=values["seo_description"],
                        )
                    )
                for order, researcher in enumerate(researchers[:2]):
                    self._save(
                        PublicationAuthor(
                            publication=publication,
                            researcher=researcher,
                            display_order=order,
                        )
                    )
                self._save(
                    PublicationAuthor(
                        publication=publication,
                        external_name="[DEMO] Colaborador externo",
                        display_order=2,
                    )
                )
                self._publish(publication, self._status(number, 4))

    def _courses(self) -> None:
        types = Course.CourseType.values
        for number in range(1, 9):
            course, created = self._record(
                Course,
                {"external_url": f"https://example.org/npca-demo/courses/{number}"},
                {
                    "course_type": types[(number - 1) % len(types)],
                    "is_featured": number <= 4,
                    "display_order": number,
                    "created_by": self.editor,
                    "updated_by": self.editor,
                },
            )
            if created:
                self._image(course, "cover", number)
                course.cover_credit = "Imagem ilustrativa do pacote de seed do LabCompAp"
                for language in LANGUAGES:
                    values = content(TOPICS[(number - 1) % 5], language, number)
                    self._save(
                        CourseTranslation(
                            course=course,
                            language=language,
                            title=values["title"],
                            summary=values["summary"],
                            cover_alt_text="Imagem ilustrativa do laboratório"
                            if language == "pt-br"
                            else "Illustrative laboratory image",
                        )
                    )
                self._publish(course, self._status(number, 6))

    def _labcompap(self) -> None:
        equipment_names = (
            ("Estação de trabalho", "Workstation"),
            ("Kit de sensores", "Sensor kit"),
            ("Servidor de experimentos", "Experimental server"),
        )
        for number, names in enumerate(equipment_names, start=1):
            equipment, created = self._record(
                LabEquipment,
                {"inventory_code": f"DEMO-EQ-{number:02d}"},
                {
                    "name_pt_br": f"[DEMO] {names[0]}",
                    "name_en": f"[DEMO] {names[1]}",
                    "brand": "Marca fictícia",
                    "model_name": f"Modelo demonstrativo {number}",
                    "display_order": 100 + number,
                },
            )
            if created:
                self._save(equipment)
            image, created = self._record(
                LabGalleryImage,
                {"credit": f"[DEMO] Imagem ilustrativa {number:02d}"},
                {
                    "alt_text_pt_br": f"Imagem ilustrativa do laboratório {number}",
                    "alt_text_en": f"Illustrative laboratory image {number}",
                    "caption_pt_br": f"[DEMO] Galeria de teste {number}",
                    "caption_en": f"[DEMO] Test gallery {number}",
                    "display_order": 100 + number,
                },
            )
            if created:
                self._image(image, "image", number)
                self._save(image)
