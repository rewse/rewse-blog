class Image:
    width: int

    @classmethod
    def new_from_file(cls, vips_filename: str, **kwargs: object) -> "Image": ...

    def heifsave(
        self,
        filename: str,
        *,
        Q: int,
        compression: str,
        strip: bool,
    ) -> None: ...

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
