import copy
import json
import io
from contextlib import redirect_stdout
from pypdf import PdfReader

from app.cli.check import show
from app.features.reports.service import build_report
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.features.ad_review.checks import finalize
import app.features.ad_review.audit as verification
import app.features.ad_review.service as pipeline

DESC = '''1. ALL TEXT: ACME bottled water. Pure refreshment.
2. PRODUCT: ACME bottled water, beverage.
3. CLAIMS: NONE
4. WARNINGS AND FINE PRINT: NONE FOUND
5. PEOPLE: No people or revealing clothing are shown.
6. OTHER VISUALS: A clear bottle on a white background.
7. UNREADABLE: NONE'''


def approval():
    return {'verdict':'COMPLIANT', 'category_rule':'NONE', 'approval_summary':'The observed ad meets the checked requirements.', 'reasons':[],
            'checks_passed':[
                {'check':'General standards','guideline':'G-01','finding':'The ad shows bottled water.','evidence':'ACME bottled water'},
                {'check':'Decency','guideline':'G-04','finding':'No people are shown.','evidence':'No people or revealing clothing are shown.'},
                {'check':'Presentation','guideline':'G-01','finding':'A product bottle is visible.','evidence':'A clear bottle on a white background.'},
                {'check':'Text','guideline':'G-01','finding':'The brand is visible.','evidence':'ACME bottled water. Pure refreshment.'},
            ]}


def finding(**kwargs):
    return dict({'rule':'G-01','problem':'An unsupported claim appears.','suggestion':'Remove the claim.','evidence':'ACME bottled water'}, **kwargs)


def rejection(reason=None):
    return {'verdict':'NON-COMPLIANT','category_rule':'NONE','reasons':[reason or finding()]}


class AccurateVerificationTests(unittest.TestCase):
    def check_result(self, data, description=DESC):
        return finalize(json.dumps(data), description)

    def test_valid_approval_and_negated_decency(self):
        self.assertEqual(self.check_result(approval())['result'],'COMPLIANT')

    def test_discarded_rejection_approves_with_notes(self):
        result=self.check_result(rejection(finding(evidence='A celebrity smoking a cigarette')))
        self.assertEqual(result['result'],'COMPLIANT')
        self.assertTrue(result['removed_reasons'])
        self.assertTrue(result['notes'])

    def test_empty_or_unknown_judgment_never_approves(self):
        for data in [{}, {'verdict':'OK','reasons':[]}, {'verdict':'COMPLIANT','reasons':'bad'}, {'verdict':'COMPLIANT','reasons':[None]}]:
            self.assertEqual(self.check_result(data)['result'],'ERROR')
        self.assertEqual(self.check_result(approval(),'')['result'],'ERROR')

    def test_unsupported_rule_or_paraphrased_evidence_approves_with_notes(self):
        for reason in [finding(rule='G-99'), finding(evidence='water ACME refreshment bottled'), finding(problem='')]:
            self.assertEqual(self.check_result(rejection(reason))['result'],'COMPLIANT')

    def test_supported_rejection_kept_for_independent_audit(self):
        self.assertEqual(self.check_result(rejection())['result'],'NON-COMPLIANT')

    def test_unreadable_or_incomplete_observations_approve_with_notes(self):
        self.assertEqual(self.check_result(approval(),DESC.replace('7. UNREADABLE: NONE','7. UNREADABLE: Bottom-right text is blurry.'))['result'],'COMPLIANT')
        self.assertEqual(self.check_result(approval(),DESC.split('7. UNREADABLE')[0])['result'],'COMPLIANT')

    def test_missing_checks_or_evidence_approve_with_notes(self):
        for field in ['evidence','guideline','finding']:
            data=approval();del data['checks_passed'][0][field]
            self.assertEqual(self.check_result(data)['result'],'COMPLIANT')
        data=approval();data['checks_passed']=[]
        self.assertEqual(self.check_result(data)['result'],'COMPLIANT')

    def test_unknown_category_or_contradictory_category_approve_with_notes(self):
        self.assertEqual(self.check_result(approval(),DESC.replace('ACME bottled water, beverage.','UNKNOWN product.'))['result'],'COMPLIANT')
        data=approval();data['category_rule']='R-ALC'
        self.assertEqual(self.check_result(data)['result'],'COMPLIANT')

    def test_incomplete_approval_explains_specific_gaps(self):
        data = approval()
        data['checks_passed'] = [data['checks_passed'][0]]
        result = self.check_result(data)
        self.assertEqual(result['result'], 'COMPLIANT')
        self.assertIn('Notes:', result['explanation'])
        self.assertIn('Only 1 of the required 4', result['message'])
        self.assertIn('Decency (G-04)', result['message'])
        self.assertNotIn('General advertising standards were not verified', result['message'])

    def test_unmatched_check_explains_evidence_gap(self):
        data = approval()
        data['checks_passed'][1]['evidence'] = 'People standing in a park'
        result = self.check_result(data)
        self.assertEqual(result['result'], 'COMPLIANT')
        self.assertIn('Decency: the quoted evidence could not be matched', result['message'])

    def test_completed_verdicts_have_explanations(self):
        self.assertEqual(self.check_result(approval())['explanation'], approval()['approval_summary'])
        result = self.check_result(rejection())
        self.assertIn('Not approved:', result['explanation'])
        self.assertIn(finding()['problem'], result['explanation'])

    def test_unchecked_claim_adds_notes(self):
        desc=DESC.replace('3. CLAIMS: NONE','3. CLAIMS: "Pure refreshment"')
        data=approval();data['checks_passed'][3]['evidence']='ACME bottled water'
        self.assertEqual(self.check_result(data,desc)['result'],'COMPLIANT')

    def test_decency_keyword_only_requests_review_not_rejection(self):
        desc=DESC.replace('No people or revealing clothing are shown.','An adult is wearing swimwear.')
        self.assertEqual(self.check_result(approval(),desc)['result'],'COMPLIANT')

    def test_negated_decency_rejection_is_not_kept(self):
        reason=finding(rule='G-04', evidence='No people or revealing clothing are shown.',problem='Revealing clothing is shown.')
        self.assertEqual(self.check_result(rejection(reason))['result'],'COMPLIANT')
        self.assertEqual(self.check_result(rejection(reason))['reasons'],[])

    def test_required_statement_absence_needs_complete_readable_text(self):
        desc=DESC.replace('ACME bottled water, beverage.','ACME beer, alcoholic beverage.')
        data=rejection(finding(rule='R-ALC',evidence='MISSING: DRINK RESPONSIBLY'))
        data['category_rule']='R-ALC'
        self.assertEqual(self.check_result(data,desc)['result'],'NON-COMPLIANT')
        self.assertEqual(self.check_result(data,desc.replace('7. UNREADABLE: NONE','7. UNREADABLE: Small legal line unreadable'))['result'],'COMPLIANT')
        self.assertEqual(self.check_result(data,desc.replace('1. ALL TEXT:','1. ALL TEXT: DRINK RESPONSIBLY.'))['result'],'COMPLIANT')
        data['reasons'][0]['evidence']='MISSING: FDA APPROVED'
        self.assertEqual(self.check_result(data,desc)['result'],'COMPLIANT')

    def test_judge_review_issues_preserved_as_notes(self):
        data=approval();data.update(verdict='NEEDS_REVIEW',review_issues=['Need a permit.'])
        result=self.check_result(data)
        self.assertEqual(result['result'],'COMPLIANT')
        self.assertIn('Need a permit.',result['message'])
        self.assertIn('Need a permit.',result['notes'])

    def test_incomplete_approval_explains_supported_checks(self):
        data = approval()
        data['checks_passed'] = [data['checks_passed'][0]]
        result = self.check_result(data)
        self.assertIn('General standards: The ad shows bottled water.', result['approval_summary'])
        self.assertNotIn('Decency:', result['approval_summary'])

    def test_approval_without_passing_checks_explains_policy_basis(self):
        result = self.check_result(rejection(finding(evidence='Unobserved celebrity')))
        self.assertIn('no proposed rule violation could be verified', result['approval_summary'])
        self.assertIn('no passing checks were established', result['approval_summary'])

    def test_whiskey_observation_conflict_is_not_a_violation(self):
        desc = """1. ALL TEXT: Drink Responsibly (top right, large)
RESERVE OAK WHISKEY
SMALL BATCH
AGED IN AMERICAN OAK
2. PRODUCT: RESERVE OAK WHISKEY, alcoholic beverage.
3. CLAIMS: "SMALL BATCH", "AGED IN AMERICAN OAK"
4. WARNINGS AND FINE PRINT: NONE FOUND
5. PEOPLE: NONE
6. OTHER VISUALS: A whiskey bottle and a glass with ice in a bar setting.
7. UNREADABLE: Small text on the neck of the bottle."""
        cases = [
            ('Drink Responsibly (top right, large)', "The mandatory statement is present, but the description notes NONE FOUND under warnings and fine print, and the text on the neck of the bottle is unreadable."),
            ('NONE FOUND', 'The warnings section contradicts the overall text.'),
            ('Small text on the neck of the bottle.', 'The mandatory information is not clearly legible.'),
        ]
        for evidence, problem in cases:
            with self.subTest(evidence=evidence):
                data = rejection(finding(rule='R-ALC', evidence=evidence, problem=problem))
                data['category_rule'] = 'R-ALC'
                result = self.check_result(data, desc)
                self.assertEqual(result['result'], 'COMPLIANT')
                self.assertEqual(result['reasons'], [])
                self.assertTrue(result['removed_reasons'])
                self.assertTrue(result['notes'])

    def test_specific_prominence_and_drinking_violations_still_reject(self):
        for observation, problem in [
            ('DRINK RESPONSIBLY is tiny and faint.', 'The mandatory statement is not prominent.'),
            ('An adult is drinking whiskey.', 'The ad shows the act of drinking.'),
        ]:
            desc = DESC.replace('ACME bottled water, beverage.', 'ACME whiskey, alcoholic beverage.')
            desc = desc.replace('A clear bottle on a white background.', observation)
            data = rejection(finding(rule='R-ALC', evidence=observation, problem=problem))
            data['category_rule'] = 'R-ALC'
            self.assertEqual(self.check_result(data, desc)['result'], 'NON-COMPLIANT')

    def test_cli_and_pdf_preserve_decisions_and_notes(self):
        for verdict, label in [('COMPLIANT', 'Approve'), ('NON-COMPLIANT', 'Reject'), ('NEEDS_REVIEW', 'Approve')]:
            data = {'result': verdict, 'review_issues': ['Permit unverified'], 'reasons': []}
            output = io.StringIO()
            with redirect_stdout(output):
                show(data)
            self.assertIn('RESULT: ' + label, output.getvalue())
            self.assertIn('Notes:', output.getvalue())
            self.assertIn('Permit unverified', output.getvalue())
            pdf = PdfReader(io.BytesIO(build_report(data, b'no image')))
            text = '\n'.join(page.extract_text() for page in pdf.pages)
            self.assertIn(label, text)
            self.assertIn('NOTES', text)
            self.assertIn('Permit unverified', text)
            self.assertEqual(data['result'], verdict)

    def test_independent_audit_requires_explicit_consistent_success(self):
        model=Mock()
        with patch('app.features.ad_review.audit.get_judge',return_value=model):
            for body, success in [('{"supported":true,"issues":[]}',True),('{"supported":false,"issues":["Claim is unverified"]}',False),('{"supported":true,"issues":["Missing evidence"]}',False),('invalid',False)]:
                model.invoke.return_value=SimpleNamespace(text=body,response_metadata={})
                self.assertEqual(not verification.audit_judgment(approval(),DESC,['rules']),success)
            model.invoke.side_effect=RuntimeError('offline')
            self.assertTrue(verification.audit_judgment(approval(),DESC,['rules']))

    def test_audit_disagreement_never_becomes_opposite_verdict(self):
        for verdict in ['COMPLIANT','NON-COMPLIANT']:
            with patch('app.features.ad_review.service.describe_image',return_value=iter([DESC])), patch('app.features.ad_review.service.judge_stream',return_value=iter([('answer','raw')])):
                with patch('app.features.ad_review.service.finalize',return_value={'result':verdict}), patch('app.features.ad_review.service.audit_judgment',return_value=['Evidence conflicts']):
                    result=list(pipeline.check_image(b'image'))[-1][1]
            self.assertEqual(result['result'],verdict)
            self.assertIn('Evidence conflicts', result['notes'])
            self.assertEqual(result['analysis']['seed'],pipeline.IMAGE_SEED)


if __name__=='__main__':
    unittest.main()
