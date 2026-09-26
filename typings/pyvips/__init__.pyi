class Image:
    width: int

    @classmethod
    def black(cls, width: int, height: int, **kwargs: object) -> "Image": ...

    @classmethod
    def new_from_file(cls, vips_filename: str, **kwargs: object) -> "Image": ...

    def get_fields(self) -> list[str]: ...

    def heifsave(
        self,
        filename: str,
        *,
        Q: int,
        compression: str,
        strip: bool,
    ) -> None: ...

    def icc_transform(
        self,
        output_profile: str,
        *,
        embedded: bool,
        intent: str,
    ) -> "Image": ...

    def jpegsave(
        self,
        filename: str,
        *,
        Q: int,
        strip: bool,
    ) -> None: ...

    def pngsave(
        self,
        filename: str,
        *,
        compression: int,
        strip: bool,
    ) -> None: ...

    def resize(self, scale: float, **kwargs: object) -> "Image": ...
