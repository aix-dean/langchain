import copy
import json
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

    def test_discarded_rejection_is_review_not_approval(self):
        result=self.check_result(rejection(finding(evidence='A celebrity smoking a cigarette')))
        self.assertEqual(result['result'],'NEEDS_REVIEW')
        self.assertTrue(result['removed_reasons'])

    def test_empty_or_unknown_judgment_never_approves(self):
        for data in [{}, {'verdict':'OK','reasons':[]}, {'verdict':'COMPLIANT','reasons':'bad'}, {'verdict':'COMPLIANT','reasons':[None]}]:
            self.assertEqual(self.check_result(data)['result'],'ERROR')
        self.assertEqual(self.check_result(approval(),'')['result'],'ERROR')

    def test_unsupported_rule_or_paraphrased_evidence_needs_review(self):
        for reason in [finding(rule='G-99'), finding(evidence='water ACME refreshment bottled'), finding(problem='')]:
            self.assertEqual(self.check_result(rejection(reason))['result'],'NEEDS_REVIEW')

    def test_supported_rejection_kept_for_independent_audit(self):
        self.assertEqual(self.check_result(rejection())['result'],'NON-COMPLIANT')

    def test_unreadable_or_incomplete_observations_cannot_approve(self):
        self.assertEqual(self.check_result(approval(),DESC.replace('7. UNREADABLE: NONE','7. UNREADABLE: Bottom-right text is blurry.'))['result'],'NEEDS_REVIEW')
        self.assertEqual(self.check_result(approval(),DESC.split('7. UNREADABLE')[0])['result'],'NEEDS_REVIEW')

    def test_missing_checks_or_evidence_cannot_approve(self):
        for field in ['evidence','guideline','finding']:
            data=approval();del data['checks_passed'][0][field]
            self.assertEqual(self.check_result(data)['result'],'NEEDS_REVIEW')
        data=approval();data['checks_passed']=[]
        self.assertEqual(self.check_result(data)['result'],'NEEDS_REVIEW')

    def test_unknown_category_or_contradictory_category_cannot_approve(self):
        self.assertEqual(self.check_result(approval(),DESC.replace('ACME bottled water, beverage.','UNKNOWN product.'))['result'],'NEEDS_REVIEW')
        data=approval();data['category_rule']='R-ALC'
        self.assertEqual(self.check_result(data)['result'],'NEEDS_REVIEW')

    def test_unchecked_claim_prevents_approval(self):
        desc=DESC.replace('3. CLAIMS: NONE','3. CLAIMS: "Pure refreshment"')
        data=approval();data['checks_passed'][3]['evidence']='ACME bottled water'
        self.assertEqual(self.check_result(data,desc)['result'],'NEEDS_REVIEW')

    def test_decency_keyword_only_requests_review_not_rejection(self):
        desc=DESC.replace('No people or revealing clothing are shown.','An adult is wearing swimwear.')
        self.assertEqual(self.check_result(approval(),desc)['result'],'NEEDS_REVIEW')

    def test_negated_decency_rejection_is_not_kept(self):
        reason=finding(rule='G-04', evidence='No people or revealing clothing are shown.',problem='Revealing clothing is shown.')
        self.assertEqual(self.check_result(rejection(reason))['result'],'NEEDS_REVIEW')
        self.assertEqual(self.check_result(rejection(reason))['reasons'],[])

    def test_required_statement_absence_needs_complete_readable_text(self):
        desc=DESC.replace('ACME bottled water, beverage.','ACME beer, alcoholic beverage.')
        data=rejection(finding(rule='R-ALC',evidence='MISSING: DRINK RESPONSIBLY'))
        data['category_rule']='R-ALC'
        self.assertEqual(self.check_result(data,desc)['result'],'NON-COMPLIANT')
        self.assertEqual(self.check_result(data,desc.replace('7. UNREADABLE: NONE','7. UNREADABLE: Small legal line unreadable'))['result'],'NEEDS_REVIEW')
        self.assertEqual(self.check_result(data,desc.replace('1. ALL TEXT:','1. ALL TEXT: DRINK RESPONSIBLY.'))['result'],'NEEDS_REVIEW')
        data['reasons'][0]['evidence']='MISSING: FDA APPROVED'
        self.assertEqual(self.check_result(data,desc)['result'],'NEEDS_REVIEW')

    def test_judge_review_status_preserved(self):
        data=approval();data.update(verdict='NEEDS_REVIEW',review_issues=['Need a permit.'])
        result=self.check_result(data)
        self.assertEqual(result['result'],'NEEDS_REVIEW')
        self.assertIn('Need a permit.',result['message'])

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
            self.assertEqual(result['result'],'NEEDS_REVIEW')
            self.assertEqual(result['analysis']['seed'],pipeline.IMAGE_SEED)


if __name__=='__main__':
    unittest.main()
