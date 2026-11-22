# فهرست APIهای سامانه — نسخه v1

همه مسیرها زیر پیشوند `/api/v1/` هستند. احراز هویت: `Authorization: Bearer <JWT>`.
مستندات تعاملی: `/api/docs` (Swagger UI)

## احراز هویت و کاربر
| روش | مسیر | کاربرد |
|---|---|---|
| POST | /auth/login | ورود و دریافت توکن |
| GET | /auth/me | پروفایل، نقش‌های سازمانی و رضایت‌ها |
| POST | /me/consents | ثبت/لغو رضایت اشتراک داده |
| GET/POST | /me/skills | مهارت‌ها و شواهد کاربر |

## سازمان‌ها
| روش | مسیر | کاربرد |
|---|---|---|
| GET | /organizations | فهرست و جست‌وجو |
| POST | /organizations | ثبت سازمان جدید (+درخواست احراز) |
| GET | /organizations/{id} | جزئیات، اعضا و سوابق احراز |
| POST | /organizations/{id}/verification-requests | درخواست احراز |
| POST | /organizations/{id}/verification | تصمیم احراز (دفتر) |
| POST | /organizations/{id}/members | افزودن عضو با نقش |
| GET | /users | جست‌وجوی کاربران (پروفایل حداقلی) |

## مسئله صنعتی
| روش | مسیر | کاربرد |
|---|---|---|
| POST | /problems | ثبت پیش‌نویس (نقش صنعت) |
| GET | /problems | فهرست با فیلتر (q، sector، work_mode، status، mine) |
| GET/PATCH | /problems/{id} | جزئیات مجاز / ویرایش نسخه‌دار |
| POST | /problems/{id}/submit | ارسال برای بررسی |
| POST | /problems/{id}/reviews | بررسی کارشناس (approve/needs_revision/reject) |
| POST | /problems/{id}/publish | انتشار با کنترل کیفیت (AC-02) |
| POST | /problems/{id}/close | بستن فراخوان |
| GET/POST | /problems/{id}/questions | پرسش و پاسخ کنترل‌شده |
| POST | /problems/{id}/interests | علاقه‌مندی |
| GET | /problems/{id}/versions | تاریخچه نسخه‌ها |
| GET | /problems/{id}/reviews | سوابق بررسی |

## درخواست همکاری
| روش | مسیر | کاربرد |
|---|---|---|
| POST | /problems/{id}/applications | ثبت درخواست (+اعضای تیم) |
| GET | /problems/{id}/applications | متقاضیان مجاز (صنعت/دفتر) |
| GET | /applications | درخواست‌های من |
| GET | /applications/{id} | جزئیات |
| POST | /applications/{id}/decisions | فهرست کوتاه/پذیرش/عدم پذیرش با دلیل (AC-07) |
| POST | /applications/{id}/members | دعوت عضو |
| POST | /applications/{id}/members/{mid}/respond | پاسخ به دعوت |
| POST | /applications/{id}/withdraw | پس گرفتن |

## تطبیق و پیشنهاد
| روش | مسیر | کاربرد |
|---|---|---|
| POST | /problems/{id}/match-runs | اجرای موتور تطبیق قواعدی |
| GET | /match-runs/{id} | وضعیت و وزن‌ها |
| GET | /match-runs/{id}/results | نتایج با دلیل و نسخه الگوریتم (AC-06) |
| GET | /me/recommended-problems | پیشنهاد مسئله به دانشجو/استاد |

## همکاری صنعتی
| روش | مسیر | کاربرد |
|---|---|---|
| POST | /collaborations | ایجاد از درخواست پذیرفته‌شده (AC-08) |
| GET | /collaborations، /collaborations/{id} | فهرست/جزئیات |
| POST | /collaborations/{id}/milestones | نقطه عطف |
| POST | /collaborations/{id}/deliverables | ثبت خروجی |
| POST | /deliverables/{id}/reviews | پذیرش/اصلاح (فقط نماینده صنعت — AC-09) |
| POST | /collaborations/{id}/status | گذار وضعیت با قواعد |
| POST | /collaborations/{id}/evaluations | ارزیابی طرف‌ها |
| PATCH | /collaborations/{id}/achievement | ثبت دستاورد نهایی |

## تحلیل و تجاری‌سازی
| روش | مسیر | کاربرد |
|---|---|---|
| GET | /analytics/summary | شاخص‌های کلیدی (بخش ۱۳ سند) |
| GET | /analytics/skill-demand | روند و نوظهورها با منبع (AC-10) |
| GET | /analytics/collaboration-network | گره‌ها/یال‌ها با ردیابی پروژه (AC-11) |
| GET | /analytics/quality | کیفیت داده |
| GET/POST | /commercialization/cases | پرونده فرصت |
| POST | /commercialization/cases/{id}/reviews | ارزیابی متخصص (AC-12) |
| POST | /commercialization/research-assets | ثبت دارایی پژوهشی |

## عمومی
| روش | مسیر | کاربرد |
|---|---|---|
| GET | /health | سلامت سرویس |
| GET | /notifications + read/read-all | اعلان‌ها |
| GET | /audit-logs | حسابرسی (مدیر فنی — AC-15) |
| POST | /attachments | بارگذاری پیوست (پسوند و اندازه محدود) |
| GET | /attachments/{id}/download | دریافت فایل |

## قراردادهای خطا
پاسخ خطا ساختاریافته است: `{"code": "...", "message": "...", "request_id": "..."}` —
کدهای رایج: `forbidden`, `forbidden_org_scope`, `confidential`, `invalid_state`,
`quality_gate_failed`, `org_not_verified`, `duplicate_application`, `reason_required`.
