---
id: 15820
severity: "High"
---

# Fund Withdrawal Flaw in preMarket Allows Users to Avoid Settlement Obligations

## Description

The goal of the protocol is to facilitate pre-market trading by allowing sellers to list points at their desired prices and enabling buyers to purchase these assets before their official launch. After the Token Generation Event (TGE), sellers are required to deliver the corresponding tokens to buyers at the pre-listed prices, ensuring that pre-market agreements are honored and enhancing overall market liquidity.

<https://tadle.gitbook.io/tadle/how-tadle-works/features-and-terminologies/settlement-and-collateral-rate>
Sellers will receive their initial collateral back along with the buyer's funds only after completing the settlement.
Buyers will receive the equivalent tokens, and their funds will be transferred to the sellers.
If sellers fail to complete the settlement within the allotted time, they will forfeit their collateral.
Buyers can claim compensation from the seller’s collateral as stored in the smart contract.

The ability for sellers to withdraw buyer's funds and tax fees before completing the settlement poses a significant risk to the integrity of the Tadle protocol. This vulnerability allows sellers to evade their settlement obligations, leaving buyers without the tokens they paid for and without any form of compensation. This not only compromises the trustworthiness of the platform but also deters potential participants, reducing market liquidity and participation.

## Proof of Concept

Scenario 1
Alice Creates an Ask Offer in Turbo Mode:
Collateral: 10,000 USDC
Points Listed: 1,000
collateral rate : 10_000 (so alice deposit exactly 10 000 usdc)
Bob Purchases Points:
Points Bought: 500
Collateral Reserved: 5,000 USDC
Dany Purchases Points:
Points Bought: 500
Collateral Reserved: 5,000 USDC
Alice Withdraws Funds:
Amount Withdrawn: 10,000 USDC + 300 USDC (taxFee)
Post-TGE Obligation :
Alice Must Settle: 500 points for Bob and 500 points for Dany.

Issue: If the value of 1,000 points in PointToken increases to 15,000 USDC after the TGE, Alice might choose not to settle her obligations. Having already withdrawn 10,300 USDC, she faces no penalty for failing to deliver the tokens and gains an additional 300 USDC. Meanwhile, Bob and Dany would not receive the tokens they paid for, and they would lose their tax fee and any potential compensation. This undermines the protocol’s integrity and leaves buyers unprotected.
working test case

```solidity
function testaskcustom() public {
        
        //create the three user and deal then usdc
        address alice = vm.addr(10);
        address bob = vm.addr(11);
        address dany = vm.addr(12);

        deal(address(mockUSDCToken), alice, 10000 );
        deal(address(mockUSDCToken), bob, 100000 );
        deal(address(mockUSDCToken), dany, 100000 );

        // alice create an ask offer
        vm.startPrank(alice);
        mockUSDCToken.approve(address(tokenManager), type(uint256).max);
        preMarktes.createOffer(
            CreateOfferParams(
                marketPlace,
                address(mockUSDCToken),
                1000,
                10000,
                10000,
                300,
                OfferType.Ask,
                OfferSettleType.Turbo
            )
        );
        address aliceOffr = GenerateAddress.generateOfferAddress(0);
        address aliceStock = GenerateAddress.generateStockAddress(0);
        vm.stopPrank();

        // bob buy 500 point
        vm.startPrank(bob);
        mockUSDCToken.approve(address(tokenManager), type(uint256).max);
        preMarktes.createTaker(aliceOffr, 500);
        address bobStock = GenerateAddress.generateStockAddress(1);
        vm.stopPrank();

        // dany buy 500 point
        vm.startPrank(dany);
        mockUSDCToken.approve(address(tokenManager), type(uint256).max);
        preMarktes.createTaker(aliceOffr, 500);
        address danyStock = GenerateAddress.generateStockAddress(2);
        vm.stopPrank();

        // alice call wthdraw and get salesRevenue an TaxIncome before settlement
        vm.startPrank(alice);
        tokenManager.withdraw(address(mockUSDCToken), TokenBalanceType.SalesRevenue);
        tokenManager.withdraw(address(mockUSDCToken), TokenBalanceType.TaxIncome);
        vm.stopPrank();
        assertEq(mockUSDCToken.balanceOf(alice),10300);

}
```

Scenario 2
Alice Creates an Bid Offer in Turbo Mode:
Collateral: 10,000 USDC
Points Listed: 1,000
Bob Sell Points to alice :
Points sold: 1 000
Collateral Reserved: 10 000 USDC
Bob Withdraws Funds:
Amount Withdrawn: 10,000 USDC

## Recommendation

Restrict Withdrawal Before Settlement: Modify the smart contract to prevent sellers from withdrawing any funds, including the sales revenue and collateral, before they have successfully completed their settlement obligations or they aborted or canceled their offer.

example
Implement a new mapping and adjust the addTokenBalance function as follows :

```solidity
function addTokenBalance(
        TokenBalanceType _tokenBalanceType,
        address _accountAddress,
        address _tokenAddress,
        uint256 _amount,
        bool withdrawAllow
    ) external onlyRelatedContracts(tadleFactory, _msgSender()) {
        userTokenBalanceMap[accountAddress][tokenAddress][
            _tokenBalanceType
        ] += _amount;

        withdrawAllowMap[accountAddress][tokenAddress][
            _tokenBalanceType
        ] = withdrawAllow;

        emit AddTokenBalance(
            _accountAddress,
            _tokenAddress,
            _tokenBalanceType,
            _amount,
            withdrawAllow
        );
    }
```
In the withdraw function, add a check to enforce this restriction:

```solidity
    bool withdrawAllow = withdrawAllowMap[_msgSender()][
            _tokenAddress
        ][_tokenBalanceType];

        if (!withdrawAllow) {
            revert Errors.Unauthorized();
        }
```

Update the withdrawAllowMap in the settlement function to allow users to withdraw their funds only after fulfilling their obligations. If a user fails to settle, they should be prevented from withdrawing any funds they are not allow to.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logic flaw in the pre‑market module that permits a seller to withdraw the buyer’s payment and the protocol’s tax fee before the mandatory settlement of the point tokens. The contract does not enforce a lock on SalesRevenue or TaxIncome balances until the seller has transferred the agreed amount of PointToken to each buyer after the Token Generation Event. Because the withdrawal function checks only a generic permission flag that is never updated during settlement, a seller can call withdraw immediately after buyers have purchased points, collect the full collateral and tax income, and then simply refuse to deliver the tokens. This can happen in Turbo mode where the settlement deadline is later than the withdrawal window. When the seller aborts, the protocol’s rules state that the seller’s collateral should be forfeited and buyers should be compensated from that collateral, but the premature withdrawal removes the funds that would have been used for compensation, leaving buyers with no tokens, no refund, and no tax reimbursement. From the user’s perspective a buyer sees that the payment they made disappears from the contract, they receive no tokens, and the expected compensation never arrives, effectively losing their entire investment. The impact is a loss of funds for buyers, a breach of trust in the platform, and a reduction in market liquidity because participants cannot rely on the settlement guarantees. The issue was uncovered during a security audit when a test case demonstrated that after creating an ask offer and having two buyers purchase points, the seller could call the withdraw functions and end up with the full 10,300 USDC while the buyers received nothing. The flaw is subtle because the withdraw functions appear normal and are not directly linked to the settlement state, making it easy to miss during casual testing. To remediate, the contract must enforce that withdrawals of SalesRevenue and TaxIncome are only allowed after the seller has successfully completed the token delivery for each buyer, or after the offer is explicitly cancelled and the collateral is appropriately handled. This can be achieved by introducing a per‑offer withdrawal permission flag that is set to false by default and only flipped to true in the settlement routine, and by rejecting any withdraw call while the settlement flag is false, thereby preventing sellers from escaping their obligations and protecting buyer funds.
