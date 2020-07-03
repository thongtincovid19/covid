import json
import locale
import re
import urllib.request
import sys
import traceback

import firebase_admin
from firebase_admin import credentials, firestore, storage
import pandas as pd
import tabula

import datasets
import localization


FIREBASE_APP_NAME = 'thongtincovid19-4dd12'
FIREBASE_PRIVATE_KEY = './thongtincovid19_serviceaccount_privatekey.json'
FIREBASE_STORAGE_BUCKET = 'gs://thongtincovid19-4dd12.appspot.com'


class TokyoPatientsDataset(datasets.CsvDataset):
    URL = 'https://stopcovid19.metro.tokyo.lg.jp/data/130001_tokyo_covid19_patients.csv'
    NAME = 'patient-tokyo'

    COL_NO = 'STT'
    COL_AREA_CODE = 'Mã vùng'
    COL_PREFECTURE = 'Tỉnh/Thành phố'
    COL_DISTRICT = 'Quận/Huyện'
    COL_PUBLISHED_DATE = 'Ngày công bố'
    COL_DOW = 'Thứ'
    COL_SYMPTOM_DATE = 'Ngày phát hiện triệu chứng'
    COL_PATIENT_ADDRESS = 'Nơi sinh sống'
    COL_PATIENT_AGE = 'Độ tuổi'
    COL_PATIENT_SEX = 'Giới tính'
    COL_PATIENT_ATTRIBUTE = 'Đặc tính'
    COL_PATIENT_STATE = 'Tình trạng'
    COL_PATIENT_SYMPTOM = 'Triệu chứng'
    COL_PATIENT_TRAVEL = 'Có lịch sử đi lại hay không'
    COL_REF = 'Tham khảo'
    COL_DISCHARGED = 'Đã ra viện hay chưa'

    def __init__(self, **kwargs):
        super().__init__(self.URL, self.NAME, **kwargs)

    def _localize(self):
        self._localize_column_names()

        # Localize data
        self.dataframe[self.COL_PREFECTURE].replace({
            '東京都': 'Tokyo'
        }, inplace=True)
        self.dataframe[self.COL_DOW].replace({
            '日': 'CN',
            '月': '2',
            '火': '3',
            '水': '4',
            '木': '5',
            '金': '6',
            '土': '7',
        }, inplace=True)
        self.dataframe[self.COL_PATIENT_ADDRESS].replace({
            **localization.PREFECTURES,
            '湖北省武漢市': 'Vũ Hán, Hồ Bắc',
            '湖南省長沙市': 'Trường Sa, Hồ Nam',
            '都内': 'Nội đô Tokyo',
            '都外': 'Ngoài Tokyo',
            '調査中': 'Đang điều tra',
        }, inplace=True)

        self._localize_age(self.COL_PATIENT_SEX)
        self._localize_age(self.COL_PATIENT_AGE)

        return self.dataframe

    def _cleanse(self, auto_drop=False):
        # Fill missing data
        self.dataframe[self.COL_PATIENT_ADDRESS].fillna('―', inplace=True)

        if auto_drop:
            # Drop meaningless columns (less than 1 unique value)
            self.dataframe.drop(columns=[
                self.COL_AREA_CODE,
                self.COL_PREFECTURE,
                self.COL_DISTRICT,
                self.COL_SYMPTOM_DATE,
                self.COL_PATIENT_ATTRIBUTE,
                self.COL_PATIENT_STATE,
                self.COL_PATIENT_SYMPTOM,
                self.COL_PATIENT_TRAVEL,
                self.COL_REF,
                self.COL_DISCHARGED,
            ], inplace=True)

        return self.dataframe


class PrefectureByDateDataset(datasets.JsonDataset):
    URL = 'https://www3.nhk.or.jp/news/special/coronavirus/data/47newpatients-data.json'
    NAME = 'prefecture-by-date'

    COL_PREFECTURE = 'Tỉnh/Thành phố'
    COL_TOTAL = 'Tổng'

    def __init__(self, **kwargs):
        super().__init__(self.URL, self.NAME, **kwargs)

    def _create_dataframe_from_json(self):
        formatted_list = []
        for pref in self.json['data47']:
            formatted_list.append([pref['name']] + pref['data'] + [sum(pref['data'])])
        dates = self.json['category']
        self.dataframe = pd.DataFrame(
            formatted_list,
            columns=[self.COL_PREFECTURE] + dates + [self.COL_TOTAL]
        )

        return self.dataframe

    def _localize(self):
        self.dataframe[self.COL_PREFECTURE].replace(localization.PREFECTURES, inplace=True)
        return self.dataframe


class PatientDetailsDataset(datasets.JsonDataset):
    URL = (
        'https://services8.arcgis.com/JdxivnCyd1rvJTrY/ArcGIS/rest/services/v2_covid19_list_csv/FeatureServer/0/'
        'query?where=1=1'
        '&geometryType=esriGeometryEnvelope'
        '&spatialRel=esriSpatialRelIntersects'
        '&resultType=none'
        '&distance=0.0'
        '&units=esriSRUnit_Meter'
        '&returnGeodetic=false'
        '&outFields=*'
        '&returnGeometry=false'
        '&featureEncoding=esriDefault'
        '&multipatchOption=xyFootprint&'
        '&applyVCSProjection=false'
        '&returnIdsOnly=false'
        '&returnUniqueIdsOnly=false'
        '&returnCountOnly=false'
        '&returnExtentOnly=false'
        '&returnQueryGeometry=false'
        '&returnDistinctValues=false'
        '&cacheHint=false'
        '&resultRecordCount=0'
        '&returnZ=false'
        '&returnM=false'
        '&returnExceededLimitFeatures=true'
        '&sqlFormat=none'
        '&f=pjson'
    )
    NAME = 'patient-all'

    COL_DATE = 'Date'

    def __init__(self, **kwargs):
        super().__init__(self.URL, self.NAME, **kwargs)

    def _create_dataframe_from_json(self):
        self.dataframe = pd.DataFrame([entry['attributes'] for entry in self.json['features']])
        return self.dataframe

    def _cleanse(self):
        self.dataframe[self.COL_DATE].fillna(0, inplace=True)
        self.dataframe[self.COL_DATE] = pd.to_datetime(self.dataframe[self.COL_DATE], unit='ms')
        self.dataframe[self.COL_DATE] = self.dataframe[self.COL_DATE].dt.strftime('%Y%m%d %H:%M')
        return self.dataframe[self.COL_DATE]


class PatientByCityTokyoDataset(datasets.JsonDataset):
    URL = 'https://raw.githubusercontent.com/tokyo-metropolitan-gov/covid19/development/data/patient.json'
    NAME = 'patient-by-city-tokyo'

    COL_CODE = 'code'
    COL_AREA = 'area'
    COL_LABEL = 'label'
    COL_RUBY = 'ruby'
    COL_COUNT = 'count'
    COL_AREA_VIETNAMESE = 'area_vietnamese'
    COL_LABEL_VIETNAMESE = 'label_vietnamese'

    def __init__(self, **kwargs):
        super().__init__(self.URL, self.NAME, **kwargs)

    def _create_dataframe_from_json(self):
        return pd.DataFrame(self.json['datasets']['data'])

    def _cleanse(self):
        self.dataframe[self.COL_CODE].fillna(0, inplace=True)
        self.dataframe[self.COL_CODE] = self.dataframe[self.COL_CODE].astype(int)

        self.dataframe[self.COL_AREA].fillna('-', inplace=True)
        self.dataframe[self.COL_RUBY].fillna('-', inplace=True)

        return self.dataframe

    def _localize(self):
        self.dataframe[self.COL_LABEL_VIETNAMESE] = self._localize_location(
            column=self.COL_LABEL,
            localization_dict=localization.TOKYO_CITIES,
            insider_keys=['東京都'],
            insider_value='Trong Tokyo',
            outsider_value='Ngoài Tokyo',
            others={'小計': 'Tổng số'},
            inplace=False,
        )
        self.dataframe[self.COL_AREA_VIETNAMESE] = self.dataframe[self.COL_AREA].replace({
            '特別区': '23 quận lớn',
            '多摩地域': 'Địa phận Tama',
            '島しょ地域': 'Các đảo nhỏ',
        })
        return self.dataframe


class PatientByCityOsakaDataset(datasets.ExcelDataset):
    URL = 'https://github.com/codeforosaka/covid19/blob/development/data/patients_and_inspections.xlsx?raw=true'
    NAME = 'patient-by-city-osaka'
    SHEET = 1
    HEADER = 1

    COL_ID = 'Id'
    COL_PUBLISHED_DATE = 'Published date'
    COL_AGE = 'Age'
    COL_SEX = 'Sex'
    COL_LOCATION = 'Location'
    COL_SYMPTOM_DATE = 'Symptom date'
    COL_STATUS = 'Status'
    COL_DISCHARGED = 'Discharged'

    def __init__(self, **kwargs):
        super().__init__(self.URL, self.NAME, self.SHEET, self.HEADER, **kwargs)

    def _cleanse(self):
        self.dataframe[self.COL_PUBLISHED_DATE] = self.dataframe[self.COL_PUBLISHED_DATE].astype(str)
        self.dataframe[self.COL_SYMPTOM_DATE] = self.dataframe[self.COL_SYMPTOM_DATE].astype(str)
        return self.dataframe

    def _localize(self):
        self._localize_column_names()
        self._localize_age(self.COL_AGE)
        self._localize_sex(self.COL_SEX)
        self._localize_location(
            column=self.COL_LOCATION,
            localization_dict=localization.OSAKA_CITIES,
            insider_keys=['大阪府'],
            insider_value='Trong phủ',
            outsider_value='Ngoài phủ',
        )

        self.dataframe[self.COL_DISCHARGED].replace({
            '退院': 'Ra viện',
            '死亡退院': 'Tử vong',
            '入院中': 'Đang nằm viện',
            '入院調整中': 'Chuẩn bị nhập viện',
            '管外': 'Không quản lý',
        }, inplace=True)

        return self.dataframe


class PatientByCitySaitamaDataset(datasets.PdfDataset):
    BASE_URL = 'https://www.pref.saitama.lg.jp/'
    URL = 'https://www.pref.saitama.lg.jp/a0701/covid19/jokyo.html'
    NAME = 'patient-by-city-saitama'

    COL_ID = 'Id'
    COL_REF = 'Ref'
    COL_DATE = 'Date'
    COL_AGE = 'Age'
    COL_SEX = 'Sex'
    COL_LOCATION = 'Location'

    def __init__(self, **kwargs):
        super().__init__(self._find_url(), self.NAME, include_header=False, **kwargs)

    def _find_url(self):
        request = urllib.request.Request(self.URL, headers=datasets.QUERY_HEADERS)
        with urllib.request.urlopen(request) as url:
            dom = url.read().decode()

        pattern = r'<a [^>]*href="([^"]+)">陽性確認者一覧[^<]*</a>'
        url = re.search(pattern, dom).group(1)
        return f'{self.BASE_URL}{url}'

    def _localize(self):
        self.dataframe = self.dataframe.iloc[:, 1:]
        self._localize_column_names()
        self.dataframe.drop(index=0, inplace=True)
        self._localize_date(self.COL_DATE)
        self._localize_age(self.COL_AGE)
        self._localize_sex(self.COL_SEX)
        self._localize_location(
            column=self.COL_LOCATION,
            localization_dict=localization.SAITAMA_CITIES,
            insider_keys=['埼玉県', '川口市外'],
        )

        return self.dataframe


class PatientByCityKanagawaDataset(datasets.CsvDataset):
    URL = 'http://www.pref.kanagawa.jp/osirase/1369/data/csv/patient.csv'
    NAME = 'patient-by-city-kanagawa'

    COL_DATE = 'Date'
    COL_LOCATION = 'Location'
    COL_AGE = 'Age'
    COL_SEX = 'Sex'

    def __init__(self, **kwargs):
        super().__init__(self.URL, self.NAME, **kwargs)

    def _localize(self):
        self._localize_column_names()
        self._localize_age(self.COL_AGE)
        self._localize_sex(self.COL_SEX)

        self.dataframe[self.COL_LOCATION] = self.dataframe[self.COL_LOCATION].str.replace('神奈川県', '')
        self.dataframe[self.COL_LOCATION] = self.dataframe[self.COL_LOCATION].str.replace('内', '')
        self.dataframe[self.COL_LOCATION] = self.dataframe[self.COL_LOCATION].str.replace('保健所管', '')
        self.dataframe[self.COL_LOCATION] = self.dataframe[self.COL_LOCATION].str.replace('及び都', '')
        self.dataframe[self.COL_LOCATION] = self.dataframe[self.COL_LOCATION].str.replace('保健福祉事務所管', '市')
        self._localize_location(
            column=self.COL_LOCATION,
            localization_dict=localization.KANAGAWA_CITIES,
            insider_keys=['', '神奈川県', '川崎市外（川崎市発表）', '川崎市外', '横浜市外'],
            outsider_keys=['スペイン（横浜市発表）', '国外（川崎市発表）', '東京都\u3000']
        )

        return self.dataframe


class PatientByCityChibaDataset(datasets.JsonDataset):
    URL = 'https://raw.githubusercontent.com/civictechzenchiba/covid19-chiba/development/data/data.json'
    NAME = 'patient-by-city-chiba'

    COL_DATE_JP = 'Date_JP'
    COL_DOW = 'Day of Week'
    COL_LOCATION = 'Location'
    COL_AGE = 'Age'
    COL_SEX = 'Sex'
    COL_DISCHARGED = 'Discharged'
    COL_DATE = 'Date'

    def __init__(self, **kwargs):
        super().__init__(self.URL, self.NAME, **kwargs)

    def _create_dataframe_from_json(self):
        return pd.DataFrame(self.json['patients']['data'])

    def _cleanse(self):
        self.dataframe.drop(columns=[self.COL_DATE_JP, self.COL_DOW], inplace=True)

    def _localize(self):
        self._localize_column_names()
        self._localize_age(self.COL_AGE)
        self._localize_sex(self.COL_SEX)
        self._localize_boolean(self.COL_DISCHARGED)

        self._localize_location(
            column=self.COL_LOCATION,
            localization_dict=localization.CHIBA_CITIES,
            insider_keys=['千葉県'],
            outsider_keys=['中国（武漢市）', 'スペイン', 'アイルランド', '南アフリカ', 'ジンバブエ', 'イギリス'],
        )

        return self.dataframe


class PatientByCityFukuokaDataset(datasets.JsonDataset):
    URL = 'https://raw.githubusercontent.com/Code-for-Fukuoka/covid19-fukuoka/development/data/data.json'
    NAME = 'patient-by-city-fukuoka'

    COL_DATE_JP = 'Date_JP'
    COL_DOW = 'Day of Week'
    COL_LOCATION = 'Location'
    COL_AGE = 'Age'
    COL_SEX = 'Sex'
    COL_DISCHARGED = 'Discharged'
    COL_DATE = 'Date'

    def __init__(self, **kwargs):
        super().__init__(self.URL, self.NAME, **kwargs)

    def _create_dataframe_from_json(self):
        return pd.DataFrame(self.json['patients']['data'])

    def _cleanse(self):
        self.dataframe.drop(columns=[self.COL_DATE_JP, self.COL_DOW], inplace=True)

    def _localize(self):
        self._localize_column_names()
        self._localize_age(self.COL_AGE)
        self._localize_sex(self.COL_SEX)
        self._localize_boolean(self.COL_DISCHARGED)

        self._localize_location(
            column=self.COL_LOCATION,
            localization_dict=localization.FUKUOKA_CITIES,
            insider_keys=['福岡県'],
        )

        return self.dataframe


class PatientByCityHyogoDataset(datasets.JsonDataset):
    URL = 'https://raw.githubusercontent.com/stop-covid19-hyogo/covid19/development/data/patients.json'
    NAME = 'patient-by-city-hyogo'

    COL_ID = 'Id'
    COL_DATE_JP = 'Date_JP'
    COL_DOW = 'Day of Week'
    COL_LOCATION = 'Location'
    COL_AGE = 'Age'
    COL_SEX = 'Sex'
    COL_DISCHARGED = 'Discharged'
    COL_REF = 'Reference'
    COL_DATE = 'Date'

    def __init__(self, **kwargs):
        super().__init__(self.URL, self.NAME, **kwargs)

    def _create_dataframe_from_json(self):
        return pd.DataFrame(self.json['data'])

    def _cleanse(self):
        self.dataframe.drop(columns=[self.COL_DATE_JP, self.COL_DOW, self.COL_REF], inplace=True)

    def _localize(self):
        self._localize_column_names()
        self._localize_age(self.COL_AGE)
        self._localize_sex(self.COL_SEX)
        self._localize_boolean(self.COL_DISCHARGED)
        self._localize_location(
            column=self.COL_LOCATION,
            localization_dict=localization.HYOGO_CITIES,
            insider_keys=['兵庫県', '神戸市外', '西宮市外'],
        )

        return self.dataframe


class ClinicDataset(datasets.CsvDataset):
    COL_ID = 'Id'
    COL_NAME = 'Name'
    COL_POSTAL_CODE = 'Postal Code'
    COL_ADDRESS = 'Address'
    COL_TEL = 'Tel'
    COL_WEBSITE = 'Website'

    def __init__(self, url, name, **kwargs):
        super().__init__(url, name, **kwargs)

    def _localize(self):
        pass

    def _cleanse(self):
        self.dataframe = self.dataframe.iloc[:, :6]

        self.dataframe.columns = [
            self.COL_ID,
            self.COL_NAME,
            self.COL_POSTAL_CODE,
            self.COL_ADDRESS,
            self.COL_TEL,
            self.COL_WEBSITE,
        ]

        self.dataframe = self.dataframe[self.dataframe[self.COL_ID].notnull()]
        self.dataframe = self.dataframe[self.dataframe[self.COL_POSTAL_CODE].notnull()]
        self.dataframe[self.COL_ID] = self.dataframe[self.COL_ID].astype(int)
        self.dataframe[self.COL_POSTAL_CODE] = self.dataframe[self.COL_POSTAL_CODE].astype(str)
        self.dataframe.fillna('なし', inplace=True)

        for column in [
            self.COL_NAME,
            self.COL_POSTAL_CODE,
            self.COL_ADDRESS,
            self.COL_TEL,
            self.COL_WEBSITE,
        ]:
            self.dataframe[column] = self.dataframe[column].str.replace('\r', '')

        return self.dataframe


def init_firebase_app():
    cred = credentials.Certificate(FIREBASE_PRIVATE_KEY)
    try:
        app = firebase_admin.initialize_app(cred, {
            'storageBucket': f'{FIREBASE_APP_NAME}.appspot.com'
        })
    except ValueError:
        app = firebase_admin.get_app()
    client = firestore.client()
    bucket = storage.bucket(app=app)

    return app, client, bucket


def get_data_from_mhlw():
    NEW_CASE_DAILY_CSV = 'https://www.mhlw.go.jp/content/pcr_positive_daily.csv'
    new_cases = pd.read_csv(NEW_CASE_DAILY_CSV)
    new_cases.columns = ['Date', 'Cases']
    cases_total = int(new_cases['Cases'].sum())
    cases_changes = int(new_cases['Cases'].to_list()[-1])
    
    RECOVERED_CSV = 'https://www.mhlw.go.jp/content/recovery_total.csv'
    recovered = pd.read_csv(RECOVERED_CSV)
    recovered.columns = ['Date', 'Cases']
    recovered_values = recovered['Cases'].to_list()
    recovered_total = int(recovered_values[-1])
    recovered_changes = int(recovered_values[-1] - recovered_values[-2])
    
    DEATH_CSV = 'https://www.mhlw.go.jp/content/death_total.csv'
    death = pd.read_csv(DEATH_CSV)
    death.columns = ['Date', 'Cases']
    death_values = death['Cases'].astype(int).to_list()
    death_total = int(death_values[-1])
    death_changes = int(death_values[-1] - death_values[-2])
    
    return (cases_total, cases_changes), (recovered_total, recovered_changes), (death_total, death_changes)


def update_cases_recovered_deaths(bucket):
    try:
        print('Getting overall data from MHLW')
        (total_cases, total_cases_changes), (discharged, discharged_changes), (death, death_changes) = get_data_from_mhlw()
        print(f'Queried data successfully')
        storage_ref = f'overall.json'
        blob = bucket.blob(storage_ref)
        blob.upload_from_string(json.dumps({
            'total_cases': total_cases,
            'total_cases_changes': total_cases_changes,
            'discharged': discharged,
            'discharged_changes': discharged_changes,
            'death': death,
            'death_changes': death_changes
        }), content_type='application/json')
        print(f'Uploaded JSON to Firebase storage')
    except Exception as e:
        print('Failed to crawl data from MHLW')
        traceback.print_exc()


def update_clinic(bucket):
    for pref in localization.PREFECTURES.values():
        dataset = ClinicDataset(
            f'clinics/tabula-{pref.lower()}.csv',
            f'clinic-{pref.lower()}',
        )
        print(f'Dataset: {dataset.name}')
        dataset.query_all()
        print(f'Queried data successfully')
        dataset.upload_to_storage(bucket)
        print(f'Uploaded JSON to Firebase storage')
        print('-'*20)


def update_detailed_data(bucket):
    all_datasets = (
        TokyoPatientsDataset(),
        PrefectureByDateDataset(),
        # PatientDetailsDataset(),
        PatientByCityTokyoDataset(),
        PatientByCityOsakaDataset(),
        PatientByCitySaitamaDataset(),
        PatientByCityKanagawaDataset(encoding='cp932'),
        PatientByCityChibaDataset(),
        PatientByCityFukuokaDataset(),
        PatientByCityHyogoDataset(),
    )

    for dataset in all_datasets:
        try:
            print(f'Dataset: {dataset.name}')
            dataset.query_all()
            print(f'Queried data successfully')
            # dataset.save_csv()
            # print(f'Created local CSV file')
            dataset.upload_to_storage(bucket)
            print(f'Uploaded JSON to Firebase storage')
            print('-'*20)
        except Exception:
            print(f'Failed to get dataset {dataset.name}')
            traceback.print_exc()


def main(args=None):
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    app, client, bucket = init_firebase_app()
    update_cases_recovered_deaths(bucket)
    print('-' * 20)
    # update_clinic(bucket)
    # update_detailed_data(bucket)

    return 0


if __name__ == '__main__':
    sys.exit(main())
